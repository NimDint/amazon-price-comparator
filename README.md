
# Amazon Price Comparison

This project is a Python-based web automation and scraping tool that makes use of Selenium WebDriver with Chrome browser and is initiated using FastAPI. In this README, you will find instructions on how to set up your environment and install the necessary dependencies for this project.

## Python Libraries Installation

First, ensure that you have Python 3 installed on your system. If not, download it from the official Python website (https://www.python.org/downloads/).

Create a virtual environment for the project to keep your dependencies organized:

    python -m venv project_env

Activate the virtual environment:

On Windows:

    project_env\Scripts\activate

On macOS and Linux:

    source project_env/bin/activate

Install the required Python libraries using the following command:

    pip install -r requirements.txt

This command will install the following libraries:

fastapi: A modern, high-performance web framework for building APIs with Python.

uvicorn: An ASGI server to run your FastAPI application.

selenium: Provides the WebDriver API for browser automation and interaction.

pandas: A powerful data manipulation library, used for handling and exporting the scraped data.

## Running the FastAPI Application

Once you have completed the setup, you can start your FastAPI application by running the following command:

    uvicorn main:app --reload
    
This command will run the FastAPI application using Uvicorn with hot-reloading enabled. Make sure to replace main with the name of your FastAPI application file (without the .py extension) and app with the name of your FastAPI app instance.

By default, the application will be accessible at http://127.0.0.1:8000. You can interact with the API using your browser.

To view the automatically generated API documentation, visit http://127.0.0.1:8000/docs or http://127.0.0.1:8000/redoc in your browser.

## Usage

With the FastAPI application running, you can start using the project by sending requests to the appropriate API endpoints.

Open the application in your browser by opening the local host http://127.0.0.1:8000/, and use freely.

**NOTE**: For better results, the price scraping might take a moment so please be patient :)

## Live Currency

To use live currency exchange rates, get an API key from APILayer Exchange Rates Data API (available for free - https://apilayer.com/marketplace/exchangerates_data-api), and place in 'main.py' row 218:

```python
headers = {
    "apikey": "your_api_key"    # place API key
}
```
