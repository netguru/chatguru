"""Product document structure and utilities for RAG."""

from typing import NotRequired, TypedDict

from langchain_core.documents import Document


class ProductData(TypedDict):
    """Product data structure matching products.json schema."""

    id: str
    name: str
    category: str
    brand: str
    price: float
    description: str
    sizes: list[str]
    colors: list[str]
    material: str
    care_instructions: str
    in_stock: bool
    url: NotRequired[str]


def create_product_document(product: ProductData) -> Document:
    """
    Convert product data to a searchable document.

    Args:
        product: Product data dictionary

    Returns:
        LangChain Document with content and metadata
    """
    url = product.get("url")

    content = f"""
{product['name']}

Category: {product['category']}
Brand: {product['brand']}
Price: ${product['price']:.2f}

{product['description']}

Available in sizes: {', '.join(product['sizes'])}
Colors: {', '.join(product['colors'])}
Material: {product['material']}
Care: {product['care_instructions']}
Status: {'In Stock' if product['in_stock'] else 'Out of Stock'}
""".strip()

    if url:
        content = f"{content}\nURL: {url}"

    metadata = {
        "product_id": product["id"],
        "name": product["name"],
        "description": product["description"],
        "category": product["category"],
        "brand": product["brand"],
        "price": product["price"],
        "in_stock": product["in_stock"],
        "colors": product["colors"],
        "sizes": product["sizes"],
        "material": product["material"],
        "care_instructions": product["care_instructions"],
        "type": "product",
    }

    if url:
        metadata["url"] = url

    return Document(page_content=content, metadata=metadata)
