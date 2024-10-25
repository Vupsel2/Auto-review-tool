import pytest
from fastapi.testclient import TestClient
from app import app
import respx


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_review_success(client):
    data = {
        "assignment_description": "Test project description",
        "github_url_repo": "https://github.com/testuser/testrepo",
        "candidate_level": "Middle"
    }

    with respx.mock(assert_all_called=True) as mock:
        repo_api_url = "https://api.github.com/repos/testuser/testrepo"
        mock.get(repo_api_url).respond(
            status_code=200,
            json={"default_branch": "main"}
        )

        tree_api_url = "https://api.github.com/repos/testuser/testrepo/git/trees/main?recursive=1"
        mock.get(tree_api_url).respond(
            status_code=200,
            json={
                "tree": [
                    {
                        "path": "main.py",
                        "type": "blob",
                        "url": "https://api.github.com/repos/testuser/testrepo/git/blobs/sha1"
                    }
                ]
            }
        )

        blob_url = "https://api.github.com/repos/testuser/testrepo/git/blobs/sha1"
        mock.get(blob_url).respond(
            status_code=200,
            json={
                "content": "cHJpbnQoJ0hlbGxvLCBXb3JsZCEnKQ==",
                "encoding": "base64"
            }
        )

        mistral_api_url = "https://api.mistral.ai/v1/chat/completions"
        mock.post(mistral_api_url).respond(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "This is a test review from Mistral AI."
                        }
                    }
                ]
            }
        )

        response = client.post("/review", json=data)
        assert response.status_code == 200
        json_response = response.json()
        assert "review" in json_response
        assert json_response["review"] == "This is a test review from Mistral AI."

def test_review_invalid_candidate_level(client):
    data = {
        "assignment_description": "Project description",
        "github_url_repo": "https://github.com/testuser/testrepo",
        "candidate_level": "Intern"
    }
    response = client.post("/review", json=data)
    assert response.status_code == 422
    json_response = response.json()
    assert "errors" in json_response
    assert "Value error, Invalid candidate level. Allowed values: Junior, Middle, Senior." in json_response["errors"]

def test_review_invalid_github_url(client):
    data = {
        "assignment_description": "Project description",
        "github_url_repo": "invalid_url",
        "candidate_level": "Middle"
    }
    response = client.post("/review", json=data)
    assert response.status_code == 422
    json_response = response.json()
    assert "errors" in json_response
    assert "Value error, Invalid GitHub repository URL." in json_response["errors"]

def test_review_missing_fields(client):
    data = {
        "github_url_repo": "https://github.com/testuser/testrepo",
        "candidate_level": "Middle"
    }
    response = client.post("/review", json=data)
    assert response.status_code == 422
    json_response = response.json()
    assert "errors" in json_response
    assert "field required" in json_response["errors"][0].lower()

def test_review_github_api_error(client):
    data = {
        "assignment_description": "Project description",
        "github_url_repo": "https://github.com/testuser/nonexistentrepo",
        "candidate_level": "Middle"
    }

    with respx.mock(assert_all_called=True) as mock:
        repo_api_url = "https://api.github.com/repos/testuser/nonexistentrepo"
        mock.get(repo_api_url).respond(
            status_code=404
        )

        response = client.post("/review", json=data)
        assert response.status_code == 400
        json_response = response.json()
        assert "detail" in json_response
        assert json_response["detail"] == "Failed to access GitHub repository. Check the URL and access rights."

def test_review_mistral_api_error(client):
    data = {
        "assignment_description": "Project description",
        "github_url_repo": "https://github.com/testuser/testrepo",
        "candidate_level": "Middle"
    }

    with respx.mock(assert_all_called=True) as mock:
        repo_api_url = "https://api.github.com/repos/testuser/testrepo"
        mock.get(repo_api_url).respond(
            status_code=200,
            json={"default_branch": "main"}
        )

        tree_api_url = "https://api.github.com/repos/testuser/testrepo/git/trees/main?recursive=1"
        mock.get(tree_api_url).respond(
            status_code=200,
            json={
                "tree": [
                    {
                        "path": "main.py",
                        "type": "blob",
                        "url": "https://api.github.com/repos/testuser/testrepo/git/blobs/sha1"
                    }
                ]
            }
        )

        blob_url = "https://api.github.com/repos/testuser/testrepo/git/blobs/sha1"
        mock.get(blob_url).respond(
            status_code=200,
            json={
                "content": "cHJpbnQoJ0hlbGxvLCBXb3JsZCEnKQ==",
                "encoding": "base64"
            }
        )

        mistral_api_url = "https://api.mistral.ai/v1/chat/completions"
        mock.post(mistral_api_url).respond(
            status_code=500,
            text='Internal Server Error'
        )

        response = client.post("/review", json=data)
        assert response.status_code == 500
        json_response = response.json()
        assert "detail" in json_response
        assert json_response["detail"] == "HTTP error when accessing Mistral AI API."
