"""
A collection of prompts for the tasks in the project.
"""

nutritional_info = """
Extract all nutritional information from this image. 
Provide the output as a JSON object with the following structure:
{
    "calories_kJ": number,
    "calories_kcal": number,
    "total_fat": number,
    "saturated_fat": number,
    "polyunsaturated_fat": number,
    "monounsaturated_fat": number,
    "trans_fat": number,
    "total_carbohydrate": number,
    "dietary_fiber": number,
    "total_sugars": number,
    "protein": number,
    "salt": number
}
Use null for any values not present in the image.
Ensure all numeric values are numbers, not strings.
"""

ticket_info = """
Extract all products/items from this image.
Provide the output as a JSON object with the following structure:
{
    "ticket_number": number,
    "date": "DD/MM/YYYY",
    "time": "HH:MM",
    "total_price": number,
    "items": [
        {
            "name": "string",
            "quantity": number,
            "total_price": number,
            "unit_price": number,
            "price_per_kg": number
        }
    ]
}
Use null for any values not present in the image.
Ensure all numeric values are numbers, not strings.
"""
