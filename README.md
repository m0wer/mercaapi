# mercaapi

Unofficial Mercadona products API with additional nutritional information.

## Description

`mercaapi` is an unofficial API that provides access to Mercadona product data,
enhanced with additional nutritional information. This project aims to offer
developers and researchers easy access to comprehensive product data from
Mercadona, including detailed nutritional facts not readily available through
official channels.

## Features

- Comprehensive product data from Mercadona
- Enhanced nutritional information for each product
- RESTful API endpoints for easy integration
- Docker support for simple deployment
- Regular updates to keep product information current

## Installation

### Prerequisites

- Docker
- Docker Compose

### Deployment with Docker

1. Clone the repository:
   ```
   git clone https://github.com/m0wer/mercaapi.git
   cd mercaapi
   ```

2. Build and run the Docker containers:
   ```
   docker-compose up -d
   ```

3. The API will be available at `http://localhost:8000` (or the port you've configured).

## Usage

Once the API is running, you can access the following endpoints:

- GET `/products`: List all products
- GET `/products/{id}`: Get details for a specific product
- GET `/categories`: List all categories
- GET `/categories/{id}`: Get products in a specific category

Example request:
```
curl http://localhost:8000/products/12345
```

For full API documentation, visit `http://localhost:8000/docs` after deploying the project.

## Development

To set up the development environment:

1. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the development server:
   ```
   uvicorn app.main:app --reload
   ```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This project is not officially affiliated with, authorized, maintained,
sponsored, or endorsed by Mercadona or any of its affiliates or subsidiaries.
This is an independent and unofficial API. Use at your own risk.

## Contact

If you have any questions or feedback, please open an issue on the GitHub
repository. For other inquiries, send an email to mercaapi (at) sgn (dot) space.
