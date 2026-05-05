# Mercadona API - Agent Skill Reference

Base URL: `https://mercaapi.sgn.space/api`
Interactive docs: `https://mercaapi.sgn.space/api/docs`
OpenAPI schema: `https://mercaapi.sgn.space/openapi.json`

## Overview

Unofficial REST API for Mercadona (Spanish supermarket) products with nutritional
information. All product data is per 100g unless noted. Nutritional info may be
null for non-food items.

---

## Endpoints

### GET /api/products/

List all products with pagination.

Parameters:
- `skip` (int, default 0) - offset
- `limit` (int, default 100, max ~5000) - number of results

```
GET /api/products/?skip=0&limit=50
```

Returns: array of `ProductPublic` objects.

---

### GET /api/products/{product_id}

Get a single product by its numeric ID.

```
GET /api/products/24511
```

Returns: `ProductPublic` object.

---

### GET /api/products/closest

Fuzzy-match products by name and/or unit price. Best endpoint for searching
ingredients or products by human-readable name.

Parameters:
- `name` (str) - product name to fuzzy search (URL-encoded)
- `unit_price` (float, optional) - filter by unit price
- `limit` (int, default 10) - max results

```
GET /api/products/closest?name=salmon+congelado&limit=5
GET /api/products/closest?name=pechuga+pollo&limit=3
GET /api/products/closest?name=avena+copos&limit=2
```

Returns: array of `ProductMatch` objects:
```json
[
  {
    "score": 0.95,
    "product": { ... ProductPublic ... }
  }
]
```

Results are ranked by fuzzy match score. Always take the first few results and
validate manually - fuzzy matching can return unrelated products at low scores.

---

### GET /api/categories/

List all product categories.

```
GET /api/categories/
```

Returns: array of `CategoryPublic` with `id`, `name`, `parent_id`.

---

### POST /api/ticket/

Upload a Mercadona receipt (image or PDF) and get AI-extracted product matches
with nutritional stats.

Form data (multipart):
- `file` (file, optional) - image or PDF file
- `url` (str, optional) - URL to fetch the receipt from

One of `file` or `url` is required.

Returns: `TicketStats` with matched items and per-item nutritional calculations.

---

### POST /api/reports/wrong-match

Report an incorrect product match.

Body: `{ "ticket_item_id": int }`

---

### POST /api/reports/wrong-nutrition

Report incorrect nutritional data.

Body: `{ "product_id": str }`

---

## Data Models

### ProductPublic

```json
{
  "id": "24511",
  "ean": "8480000245113",
  "slug": "lomos-salmon-hacendado",
  "brand": "Hacendado",
  "name": "Lomos de salmón sin piel y sin espinas Hacendado congelado",
  "price": 6.40,
  "category_id": 42,
  "description": "...",
  "origin": null,
  "packaging": "Paquete",
  "unit_name": "ud.",
  "unit_size": 0.25,
  "is_variable_weight": false,
  "is_pack": false,
  "is_food": true,
  "category": { "id": 42, "name": "Pescados congelados", "parent_id": 5 },
  "images": [
    {
      "zoom_url": "https://prod-mercadona.imgix.net/...",
      "regular_url": "...",
      "thumbnail_url": "...",
      "perspective": 1,
      "id": 123,
      "product_id": "24511"
    }
  ],
  "nutritional_information": {
    "calories": 224.0,
    "total_fat": 16.0,
    "saturated_fat": 3.5,
    "polyunsaturated_fat": null,
    "monounsaturated_fat": null,
    "trans_fat": null,
    "total_carbohydrate": 0.0,
    "dietary_fiber": 0.0,
    "total_sugars": 0.0,
    "protein": 20.0,
    "salt": 0.3,
    "id": 999,
    "product_id": "24511"
  },
  "price_history": []
}
```

All nutritional values are per 100g. Fields may be null if not available.
`is_food: true` means the product has nutritional information.

### unit_size

`unit_size` is in kg (or L for liquids). Examples:
- `0.25` = 250g pack (e.g. one salmon loin)
- `1.0` = 1kg (e.g. broccoli bag)
- `6.0` = 6L (e.g. milk 6-pack)

For packs (`is_pack: true`), `unit_size` is the total pack weight.

---

## Nutritional Calculations

All values in `nutritional_information` are per 100g of product.

To calculate for a given portion (in grams):
```
nutrient_amount = (nutrient_per_100g / 100) * portion_grams
```

Example: 250g salmon loin (224 kcal/100g, 20g protein/100g):
- Calories: (224 / 100) * 250 = 560 kcal
- Protein: (20 / 100) * 250 = 50g

---

## Common Search Queries (Spanish product names)

Proteins:
- `salmon congelado` or `lomos salmon`
- `pechuga pollo` or `tiras pechuga pollo`
- `carne picada vacuno` or `carne picada`
- `filetes lomo cerdo`
- `secreto iberico`
- `jamon serrano`
- `atun natural`
- `huevos`

Dairy / protein:
- `queso fresco batido`
- `yogur griego`
- `kefir natural`
- `leche semidesnatada`

Carbs:
- `arroz redondo`
- `pan molde integral`
- `pasta`
- `copos avena`

Vegetables:
- `brocoli congelado`
- `edamame`
- `tomate frito`

Other:
- `aguacate`
- `semillas chia`
- `chocolate negro 85`

---

## Tips for AI Agents

1. Always use `/api/products/closest` for ingredient searches - it handles
   Spanish and partial matches via fuzzy matching.

2. Check `nutritional_information` for null before calculating macros. Some
   products (non-food, new items) may have no nutritional data.

3. `is_food: true` is computed on the server based on whether nutritional_information
   exists and has values. Use it to filter food products when paginating all products.

4. For meal planning, calculate servings from `unit_size`:
   - A salmon pack (unit_size=0.25) = 250g = 1 serving for an adult
   - A chicken pack (unit_size=0.65) = 650g = ~3-4 servings

5. The `/api/ticket/` endpoint uses AI (Gemini) to extract items from receipts
   and match them to products. It returns per-item nutritional stats including
   `cost_per_100g_protein` and `kcal_per_euro` for value analysis.

6. Product IDs are strings (numeric), not integers. Use them as path params:
   `GET /api/products/24511`

7. The fuzzy match uses Levenshtein distance on unaccented names. Searching
   `salmon` will match `salmón`. No need to include accents.

8. When a search returns unexpected results (low score or wrong category),
   try rephrasing with more specific terms or brand names (e.g. `Hacendado`).

---

## Rate Limits and Auth

No authentication required. No documented rate limits, but be reasonable
with pagination - avoid fetching all products at once unless necessary.

---

## Example Workflow: Find macros for a meal

```python
import httpx

base = "https://mercaapi.sgn.space/api"

# 1. Search for salmon
r = httpx.get(f"{base}/products/closest", params={"name": "lomos salmon", "limit": 1})
product = r.json()[0]["product"]

# 2. Get nutritional info
ni = product["nutritional_information"]
portion_g = 250  # one loin

if ni:
    kcal = round(ni["calories"] * portion_g / 100)
    protein = round(ni["protein"] * portion_g / 100, 1)
    fat = round(ni["total_fat"] * portion_g / 100, 1)
    print(f"{product['name']}: {kcal} kcal, {protein}g protein, {fat}g fat")
```
