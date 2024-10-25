# Auto-review-tool


This project is a web application built with **FastAPI** that interacts with the GitHub and Mistral AI APIs to analyze project code and provide feedback.

## Description

The application allows you to:

- Retrieve code from a specified GitHub repository.
- Send the code along with the assignment description and candidate level to Mistral AI for analysis.
- Receive and display feedback on the candidate's project.

## Requirements

- **Python 3.7** or higher
- [**Poetry**](https://python-poetry.org/docs/#installation) installed
- Mistral AI account and API key

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your_username/your_repository.git
   cd your_repository
   ```

2. **Install dependencies using Poetry:**

   ```bash
   poetry install
   ```

3. **Create a `.env` file in the root directory and add your Mistral AI API key:**

   ```env
   MISTRAL_API_KEY=your_api_key
   ```

## Running the Application

1. **Activate the Poetry virtual environment:**

   ```bash
   poetry shell
   ```

2. **Run the application using Uvicorn:**

   ```bash
   uvicorn app:app --reload
   ```

   The application will be accessible at `http://127.0.0.1:8000`.

## Usage

Send a POST request to the `/review` endpoint with JSON data in the following format:

```json
{
  "assignment_description": "Description of the assignment",
  "github_url_repo": "https://github.com/username/repository",
  "candidate_level": "Junior"  // Possible values: "Junior", "Middle", "Senior"
}
```

### Example request using `curl`:

```bash
curl -X POST "http://127.0.0.1:8000/review" 
  -H "Content-Type: application/json" 
  -d '{
    "assignment_description": "Create a simple web application",
    "github_url_repo": "https://github.com/username/repository",
    "candidate_level": "Middle"
  }'
```

## Running Tests

To run the tests, execute:

```bash
pytest tests.py
```

Ensure you are in the Poetry virtual environment.

## Project Structure

```
├── app.py          # Main application file
├── tests.py        # Test file
├── pyproject.toml  # Poetry configuration file
├── README.md       # This file
└── .env            # Environment variables file (needs to be created)
```

## Notes

- The **`.env` file** is not included in the repository and must be created manually. Do not add it to version control.
- The **`MISTRAL_API_KEY` environment variable** is required for the application to work.
- **Supported candidate levels**: "Junior", "Middle", "Senior".

#What if:

1.- Implement Caching Mechanisms:
Cache GitHub Repository Data:
Cache the file tree and metadata of repositories to avoid repeated API calls for the same data. Since repositories don't change frequently within short time spans, you can set a reasonable expiration time.
File Contents: Cache the contents of files, especially for large files or commonly accessed repositories.
Employ caching systems like Redis to store cached data in memory, which can be accessed quickly and shared across multiple instances
2. Asynchronous Processing
3. Limit the number of requests a single user can make per minute to prevent abuse. Set a global limit to control the overall load on your system.
4. Move heavy processing tasks to background workers using task queues like Celery or RQ.
5. Deploy multiple instances of the app with auto-scaling based on request load, managed through container orchestration (e.g., Kubernetes).
