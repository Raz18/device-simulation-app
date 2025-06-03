# Device Simulator Service

A FastAPI-based service that simulates IoT devices with Redis as the data store. This project includes a comprehensive test suite using pytest fixtures.

## Features

- Device management (list, get details)
- Command sending to devices
- Redis-based data storage
- Comprehensive test suite
- OpenAPI documentation

## Prerequisites

- Python 3.8+
- Redis server running locally on port 6379

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

Start the FastAPI server:
```bash
uvicorn app:app --reload
```

The API will be available at http://localhost:8000
API documentation will be available at http://localhost:8000/docs

## Running Tests

you can just simply Run the test suite:
```bash
pytest test_app.py -v
```

## API Endpoints

### GET /devices
List all simulated devices

### GET /devices/{device_id}
Get details of a specific device

### POST /devices/{device_id}/command
Send a command to a device

## Test Suite Features

- Fixtures for Redis connection management
- Test data initialization and cleanup
- Endpoint testing
- Error handling validation
- Command history verification
- OpenAPI schema validation

## Project Structure

- `app.py`: Main FastAPI application
- `test_app.py`: Test suite
- `requirements.txt`: Project dependencies
- `README.md`: Project documentation 