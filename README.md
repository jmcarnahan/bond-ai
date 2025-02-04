# Bond AI

Bond AI is a Python-based project that leverages Streamlit to create an interactive web application. The primary source code is located in the `bond_ai` directory, and the test code is in the `tests` directory. This project uses Poetry for dependency management and setup.

## Features

- Interactive web application built with Streamlit
- Integration with OpenAI for generating responses
- Google authentication support
- Modular design with agents, threads, and pages

## Getting Started

### Prerequisites

- Python 3.13
- Poetry

### Installation

1. Clone the repository:

    ```sh
    git clone https://github.com/yourusername/bond-ai.git
    cd bond-ai
    ```

2. Install dependencies using Poetry:

    ```sh
    poetry install
    ```

3. Set up environment variables:

    Create a [.env](http://_vscodecontentref_/1) file in the project root directory and add the following variables:

    ```env
    OPENAI_API_KEY=your_openai_api_key
    AZURE_OPENAI_API_KEY=your_azure_openai_api_key
    AZURE_OPENAI_ENDPOINT=your_azure_openai_endpoint
    AZURE_OPENAI_API_VERSION=2024-08-01-preview
    GOOGLE_AUTH_CREDS_PATH=path_to_your_google_auth_creds.json
    GOOGLE_AUTH_COOKIE_NAME=your_cookie_name
    GOOGLE_AUTH_COOKIE_KEY=your_cookie_key
    GOOGLE_AUTH_REDIRECT_URI=your_redirect_uri
    METADATA_DB_URL=sqlite:///.metadata.db
    ```

### Running the Application

To start the application, run the following command:

```sh
python -m bond_ai.app.start --server.port=8080 --server.address=0.0.0.0

### Running Tests

To run the tests, use the following command:

```sh
poetry run pytest
```

This will execute all the tests in the `tests` directory and provide a summary of the results.

### Contributing

We welcome contributions to the Bond AI project! To contribute, please follow these steps:

1. Fork the repository on GitHub.
2. Clone your forked repository to your local machine:

  ```sh
  git clone https://github.com/yourusername/bond-ai.git
  cd bond-ai
  ```

3. Create a new branch for your feature or bugfix:

  ```sh
  git checkout -b your-feature-branch
  ```

4. Make your changes and commit them with a descriptive message:

  ```sh
  git add .
  git commit -m "Description of your changes"
  ```

5. Push your changes to your forked repository:

  ```sh
  git push origin your-feature-branch
  ```

6. Open a pull request on the original repository and describe your changes in detail.

Thank you for contributing!