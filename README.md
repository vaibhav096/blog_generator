# AI Blog Generator

## Overview

This project is an AI-powered blog generator that transforms YouTube videos into comprehensive blog posts. It utilizes advanced technologies to provide an engaging and informative reading experience based on video content.

## Features

- **YouTube Video to Blog Conversion**: Automatically generates blog posts from YouTube videos.
- **User Authentication**: Secure login, signup, and logout functionalities.
- **Chat History**: Saves all chat interactions and responses from the Gemini model, allowing users to view their chat history upon logging in.
- **Continuous Interaction**: Allows users to continue their chat from where they left off.
- **Interactive Interface**: Simple yet interactive user interface for a seamless user experience.

## Technologies Used

- **Backend**: Python, Django
- **Frontend**: HTML5, Tailwind CSS
- **APIs**: Assembly AI, Gemini API
- **Libraries**: PyTube
- **Database**: SQLite

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/vaibhav096/blog_generator.git
    ```

2. Navigate to the project directory:
    ```sh
    cd ai_blog_app
    ```

3. Create a virtual environment and activate it:
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

4. Install the required packages:
    ```sh
    pip install -r requirements.txt
    ```

5. Set up the database:
    ```sh
    python manage.py migrate
    ```

6. Create a superuser to access the admin panel:
    ```sh
    python manage.py createsuperuser
    ```

7. Run the development server:
    ```sh
    python manage.py runserver
    ```

8. Access the application at `http://127.0.0.1:8000`.

## Usage

1. Sign up for a new account or log in with existing credentials.
2. Paste a YouTube video link to generate a blog post.
3. Interact with the chatbot to get insights and responses powered by the Gemini model.
4. View and manage your chat history.



## Acknowledgements

- Special thanks to Assembly AI and Gemini API for providing powerful AI capabilities.
- Thank you to all contributors and open-source projects that helped make this project possible.

