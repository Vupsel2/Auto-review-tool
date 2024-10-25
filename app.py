from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator, ValidationError
import httpx
import logging
from urllib.parse import urlparse
import base64
import validators
import html
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    # Extract all error messages
    error_messages = [err['msg'] for err in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={"errors": error_messages}
    )

class ReviewRequest(BaseModel):
    assignment_description: str
    github_url_repo: str
    candidate_level: str

    @field_validator('github_url_repo')
    def validate_github_url(cls, v):
        if not validators.url(v):
            raise ValueError('Invalid GitHub repository URL.')
        parsed_url = urlparse(v)
        if parsed_url.netloc != 'github.com':
            raise ValueError('URL must be a GitHub repository.')
        return v

    @field_validator('candidate_level')
    def validate_candidate_level(cls, v):
        valid_levels = ['Junior', 'Middle', 'Senior']
        if v not in valid_levels:
            raise ValueError('Invalid candidate level. Allowed values: Junior, Middle, Senior.')
        return v

async def collect_code_from_github_repo(repo_url):
    parsed_url = urlparse(repo_url)
    if parsed_url.netloc != 'github.com':
        raise ValueError('Invalid domain in GitHub repository URL.')

    path_parts = parsed_url.path.strip('/').split('/')
    if len(path_parts) < 2:
        raise ValueError('Invalid path in GitHub repository URL.')

    owner, repo_name = path_parts[0], path_parts[1]

    repo_api_url = f'https://api.github.com/repos/{owner}/{repo_name}'

    async with httpx.AsyncClient() as client:
        response = await client.get(repo_api_url)
        if response.status_code != 200:
            logger.error(f'Error fetching repository data: {response.status_code}')
            raise ValueError('Failed to access GitHub repository. Check the URL and access rights.')

        repo_data = response.json()
        default_branch = repo_data.get('default_branch', 'main')
        tree_url = f'https://api.github.com/repos/{owner}/{repo_name}/git/trees/{default_branch}?recursive=1'

        response = await client.get(tree_url)
        if response.status_code != 200:
            logger.error(f'Error fetching repository tree: {response.status_code}')
            raise ValueError('Failed to retrieve GitHub repository content.')

        tree_data = response.json()
        tree = tree_data.get('tree', [])
        code = ''
        file_list = '\nAll repository files:\n'
        max_code_length = 20000
        allowed_extensions = ['.py', '.js', '.java', '.cpp', '.c', '.cs', '.rb', '.go', '.php', '.html', '.css', '.swift', '.kt']
        file_count = 0
        max_files = 100

        for item in tree:
            if file_count >= max_files or len(code) >= max_code_length:
                break
            file_list += f"{item['path']}\n"
            if item['type'] == 'blob':
                path = item['path']
                if not any(path.endswith(ext) for ext in allowed_extensions):
                    logger.info(f'Skipping file with unsuitable extension: {path}')
                    continue
                logger.info(f'Processing file: {path}')
                blob_url = item['url']
                try:
                    blob_response = await client.get(blob_url)
                    if blob_response.status_code == 200:
                        blob_data = blob_response.json()
                        content = blob_data.get('content', '')
                        encoding = blob_data.get('encoding', '')
                        if encoding == 'base64':
                            try:
                                file_content = base64.b64decode(content).decode('utf-8')
                            except UnicodeDecodeError:
                                logger.warning(f'File {path} cannot be decoded in UTF-8, skipping.')
                                continue
                            code += f'\n\n// File: {path}\n{file_content}'
                            file_count += 1
                            if len(code) > max_code_length:
                                code = code[:max_code_length]
                                code += '\n\n// Code truncated due to size limitations.'
                                break
                        else:
                            logger.warning(f'Unknown encoding format for file {path}')
                    else:
                        logger.error(f'Error fetching file {path}: {blob_response.status_code}')
                except Exception as e:
                    logger.error(f'Error reading file {path}: {str(e)}')
        code += file_list
        return code

def get_mistral_review(prompt):
    api_url = 'https://api.mistral.ai/v1/chat/completions'
    api_key = os.getenv('MISTRAL_API_KEY')
    if not api_key:
        raise Exception('Mistral AI API key not found in environment variables.')

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    payload = {
        "model": "mistral-small-latest",
        "temperature": 0.9,
        "max_tokens": 1500,
        "min_tokens": 50,
        "stream": False,
        "random_seed": None,
        "messages": [
            {
                "role": "system",
                "content": """You are a professional code developer. Your task is to provide a review of the candidate's project.

                The structure of the response should be as follows:

                1. **Drawbacks**:
                - Brief mentions of what is missing, not done, or not considered.

                2. **Evaluation**:
                - Final score on a 5-point scale, based on the number and severity of errors and shortcomings.
                - Remember that the score should consider the level the candidate is applying for:
                    - **Junior**: Some errors and shortcomings are acceptable, as the candidate is just starting their career. A score of 5/5 means the candidate has shown excellent knowledge and potential for their level.
                    - **Middle**: Confident mastery of basic technologies and practices is expected. A score of 5/5 means the candidate performs tasks above average.
                    - **Senior**: A high level of professionalism is expected; the code should be close to ideal, following best practices and without errors. A score of 5/5 means the code is executed at an exceptional level.

                3. **Improvement Tips**:
                - Brief tips on how to improve the code.

                4. **Conclusion**:
                - A short summary of the code and the project's outcome."""
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "response_format": {
            "type": "text"
        },
        "tool_choice": "auto",
        "safe_prompt": True
    }

    try:
        with httpx.Client() as client:
            response = client.post(api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            response_json = response.json()
            try:
                choices = response_json.get('choices')
                if not choices or not isinstance(choices, list):
                    raise KeyError('Field "choices" is missing or has an incorrect format.')
                message = choices[0].get('message')
                if not message or not isinstance(message, dict):
                    raise KeyError('Field "message" is missing or has an incorrect format.')
                review_text = message.get('content')
                if not review_text:
                    raise KeyError('Field "content" is missing.')
            except KeyError as e:
                logger.error(f'Invalid response format from Mistral AI API: {e}')
                raise Exception(f'Invalid response format from Mistral AI API: {e}')
            return review_text
    except httpx.HTTPStatusError as http_err:
        logger.error(f'HTTP error when accessing Mistral AI API: {http_err.response.status_code} - {http_err.response.text}')
        raise Exception('HTTP error when accessing Mistral AI API.')
    except Exception as e:
        logger.error(f'Error when accessing Mistral AI API: {e}')
        raise Exception(f'Invalid response format from Mistral AI API: {e}')

@app.post("/review")
async def review(review_request: ReviewRequest):
    try:
        assignment_description = review_request.assignment_description
        github_url_repo = review_request.github_url_repo
        candidate_level = review_request.candidate_level

        project_code = await collect_code_from_github_repo(github_url_repo)

        # Escape project code
        safe_project_code = html.escape(project_code)

        prompt = f"""
        Please analyze the following project, paying particular attention to the fact that the candidate is applying for the {candidate_level} level, and provide feedback according to the response structure.

        Short project description: {assignment_description}

        Project code:
        {safe_project_code}
        Please provide your feedback considering the {candidate_level} vacancy level.
        """

        if len(prompt) > 20000:
            prompt = prompt[:20000]
            prompt += '\n\n// Prompt truncated due to size limitations.'

        logger.info('Sending request to Mistral AI for review.')
        review_text = get_mistral_review(prompt)
        return {'review': review_text}

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except httpx.HTTPStatusError as he:
        logger.error(f'Error accessing GitHub: {str(he)}')
        raise HTTPException(status_code=400, detail='Failed to access GitHub repository. Check the URL and access rights.')
    except Exception as e:
        logger.error(f'Internal server error: {str(e)}')
        if 'HTTP error when accessing Mistral AI API' in str(e):
            raise HTTPException(status_code=500, detail='HTTP error when accessing Mistral AI API.')
        else:
            raise HTTPException(status_code=500, detail='An internal server error occurred. Please try again later.')
