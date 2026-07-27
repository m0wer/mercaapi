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

2. Configure the environment (see `.env.example`):
   ```
   cp .env.example .env
   # Set AI_BASE_URL, AI_API_KEY and AI_MODEL (any OpenAI-compatible endpoint)
   ```

3. Build and run the Docker containers:
   ```
   docker-compose up -d
   ```

4. The API will be available at `http://localhost:8000` (or the port you've configured).

## Updating the database

The `cli.py` script parses the Mercadona API and completes nutritional
information using an OpenAI-compatible model (vision extraction from product
photos, with estimation from the product details as fallback):

```
python cli.py parse --update-existing   # products, categories, and prices
python cli.py discover-warehouses       # find warehouses from postal codes
python cli.py parse-availability        # per-warehouse availability and prices
python cli.py process-nutritional-information  # fill missing nutrition data
python cli.py clean-nutrition           # reprocess implausible nutrition rows
python cli.py update                    # all of the above, for cron
```

### Warehouse availability tracking

Mercadona serves a different catalog depending on the warehouse that covers
the customer's postal code. `discover-warehouses` probes one postal code per
province and stores the warehouse codes. `parse-availability` then walks each
warehouse's category listings and tracks, per product and warehouse:

- current availability and price (`GET /api/products/{id}/availability`)
- availability changes over time
  (`GET /api/products/{id}/availability/history`)
- price divergences from the main catalog (in the product price history)

Known warehouses are listed at `GET /api/warehouses/`. Set `active` to false
in the `warehouse` table to skip a warehouse during updates.

To run the full update periodically with Docker, add a cron entry on the host:

```
0 4 * * 0 cd /path/to/mercaapi && docker compose run --rm updater >> /var/log/mercaapi-update.log 2>&1
```

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

## Testing

To run the tests, from the repository root:

```
python3 -m pytest tests/
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
