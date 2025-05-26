# Bond AI

Bond AI leverages OpenAI's Assistant APi to help develop Generative AI agents and chatbots with access to your own tools, APIs and data sources. Bond AI also has a web UI with a built-in chat interface and is extensible to other interfaces with access to these agents. 


## Features

- Simple definition of agents with tools and data
- Automatic discovery of agents
- Built-in threads, tool access and data integration from the Assistants API
- Google authentication support
- Thread sharing between users
- Modular design with agents, threads, and pages

## Getting Started

### Prerequisites

- Python 3.12
- Poetry

### Installation

1. Clone the repository:

    ```sh
    git clone https://github.com/yourusername/bond-ai.git
    cd bond-ai
    ```

2. Install dependencies using Poetry:

    ```sh
    poetry config virtualenvs.in-project true

    poetry install

    poetry build

    poetry shell

    source $(poetry env info --path)/bin/activate
    ```

3. Set up environment variables:

    gcloud auth application-default login

    gcloud config set project <your-project-id>

    gcloud config get-value project

    Create a .env file in the project root directory and add the following variables:

    ```env
    OPENAI_API_KEY=your_openai_api_key
    OPENAI_PROJECT=you_openai_project_id
    OPENAI_DEPLOYMENT=openai_model #(e.g. "gpt-4o-mini")

    # or
    # AZURE_OPENAI_API_KEY=your_azure_openai_api_key
    # AZURE_OPENAI_ENDPOINT=your_azure_openai_endpoint
    # AZURE_OPENAI_API_VERSION=api_version (e.g. 2024-08-01-preview)
    
    AUTH_ENABLED=True
    GOOGLE_AUTH_CREDS_PATH=path_to_your_google_auth_creds.json
    GOOGLE_AUTH_REDIRECT_URI=your_redirect_uri_for_this_app

    METADATA_DB_URL=database_url_for_metadata #(e.g. sqlite:///.metadata.db)
    ```

### Running the Application

To start the application, run the following command:

```sh
python -m bond_ai.app.start --server.port=8080 --server.address=0.0.0.0
```

### Running the Frontend (Flutter UI)

The frontend is a Flutter application located in the `flutterui` directory.

**Prerequisites:**

- [Flutter SDK](https://docs.flutter.dev/get-started/install) installed on your system.

**Steps to run the frontend:**

1.  **Navigate to the Flutter project directory:**
    ```sh
    cd flutterui
    ```

2.  **Get Flutter dependencies:**
    ```sh
    flutter pub get
    ```

3.  **Run the Flutter application (web):**
    ```sh
    flutter run -d chrome --web-port 5000
    ```
    This will launch the application in a Chrome browser. You can also run it on other supported platforms (e.g., Android, iOS, desktop) if configured.

4.  **Generate Theme (if needed):**
    The project uses a script to generate theme files. If you make changes to theme configurations in `flutterui/theme_configs/` or `flutterui/lib/core/theme/base_theme.dart`, you might need to re-run the theme generation script:
    ```sh
    dart run tool/generate_theme.dart
    ```
    Or, if you are in the `flutterui` directory:
    ```sh
    dart tool/generate_theme.dart
    ```

**Working with Assets:**

- All static assets (images, fonts, etc.) should be placed in the `flutterui/assets/` directory.
- After adding new assets, ensure they are declared in the `flutterui/pubspec.yaml` file if you are not using the general `assets/` folder declaration. The current configuration `assets: - assets/` includes all files in the `assets` directory.
- You can then reference these assets in your Flutter code, for example: `Image.asset('assets/your_image.png')`.

**Customizing the Theme:**

The Flutter UI uses a theming system that allows for customization through JSON configuration files and a base theme Dart file.

1.  **Theme Configuration Files (`flutterui/theme_configs/`):**
    -   Theme configurations are defined as JSON files in the `flutterui/theme_configs/` directory (e.g., `default_theme.json`, `mcafee_config.json`).
    -   Each JSON file defines theme-specific properties like `name`, `brandingMessage`, `logo` (asset path), `logoIcon` (asset path), and Material Design color values (primary, secondary, background, etc.).
    -   **Example JSON structure:**
        ```json
        {
          "name": "My Custom Theme",
          "brandingMessage": "Welcome to my custom app!",
          "logo": "assets/custom_logo.png",
          "logoIcon": "assets/custom_icon.png",
          "themeColors": {
            "primary": "#FF0000",
            "secondary": "#00FF00",
            "background": "#FFFFFF",
            "surface": "#F0F0F0",
            "error": "#B00020",
            "onPrimary": "#FFFFFF",
            "onSecondary": "#000000",
            "onBackground": "#000000",
            "onSurface": "#000000",
            "onError": "#FFFFFF",
            "brightness": "light" // "light" or "dark"
          }
        }
        ```
    -   Ensure your logo and icon paths in the JSON correctly point to files within the `flutterui/assets/` directory.

2.  **Base Theme (`flutterui/lib/core/theme/base_theme.dart`):**
    -   The `BaseTheme` class in this file provides default values and the core structure for the theme.
    -   The theme generation script uses this `BaseTheme` as a fallback if a specific theme configuration is not found or if certain values are missing in a JSON config.
    -   You can modify `base_theme.dart` to change default behaviors or add more complex theme logic that cannot be represented in JSON.

3.  **Generating Your Theme:**
    -   After creating or modifying a theme JSON configuration (e.g., `my_theme_config.json`) or updating `base_theme.dart`, you need to run the theme generation script.
    -   This script reads the specified theme configuration (or falls back to `BaseTheme` if no config is provided) and generates `flutterui/lib/core/theme/generated_theme.dart`.
    -   The script accepts the following arguments:
        -   `-c, --config`: Path to the theme JSON configuration file.
        -   `-o, --output`: Path to output the generated Dart theme file (defaults to `lib/core/theme/generated_theme.dart` relative to the `flutterui` directory).

    -   **To generate a theme from a specific configuration file (e.g., `my_example_theme_config.json`):**
        This command must be run from the **root of the project** (e.g., the `bond-ai` directory).
        ```sh
        dart flutterui/tool/generate_theme.dart --config flutterui/theme_configs/my_example_theme_config.json --output flutterui/lib/core/theme/generated_theme.dart
        ```
        Replace `my_example_theme_config.json` with the actual name of your configuration file. The `--output` argument specifies where the `generated_theme.dart` file will be saved; the path shown is the default used by the application.

    -   **Alternative if inside the `flutterui` directory:**
        If you have navigated into the `flutterui` directory, the command would be:
        ```sh
        dart tool/generate_theme.dart --config theme_configs/my_example_theme_config.json --output lib/core/theme/generated_theme.dart
        ```

    -   **To generate a theme using the `BaseTheme` defaults (no JSON config):**
        This command also needs to be run from the appropriate directory.
        From the project root (`bond-ai`):
        ```sh
        dart flutterui/tool/generate_theme.dart --output flutterui/lib/core/theme/generated_theme.dart
        ```
        Or from the `flutterui` directory:
        ```sh
        dart tool/generate_theme.dart --output lib/core/theme/generated_theme.dart
        ```
        This will use the `BaseTheme` defined in `flutterui/lib/core/theme/base_theme.dart` as the source.

    -   The `generated_theme.dart` file is then used by the application to apply the theme. **Do not edit `flutterui/lib/core/theme/generated_theme.dart` directly**, as your changes will be overwritten the next time the script runs.

### Running Tests

To run the tests, use the following command:

```sh
poetry run pytest
```

This will execute all the tests in the `tests` directory and provide a summary of the results.

The primary source code is located in the `bond_ai` directory, and the test code is in the `tests` directory. This project uses Poetry for dependency management and setup.

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
