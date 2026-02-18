import xml.etree.ElementTree as ET

def parse_product_catalog(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    products = []
    for product_elem in root.findall('product'):
        name = product_elem.find('name').text if product_elem.find('name') is not None else None
        price = product_elem.find('price').text if product_elem.find('price') is not None else None
        description = product_elem.find('description').text if product_elem.find('description') is not None else None
        products.append({
            'name': name,
            'price': price,
            'description': description
        })
    return products
