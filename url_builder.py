def build_urls(resolved):
    location = resolved["location"].lower().replace(" ", "-")
    max_price = resolved["budget"].get("max")

    urls = []

    if "property24" in resolved["sources"]:
        urls.append(
            f"https://www.property24.com/for-sale/{location}/all-residential-properties"
        )

    if "privateproperty" in resolved["sources"]:
        urls.append(
            f"https://www.privateproperty.co.za/for-sale/{location}"
        )

    if "gumtree" in resolved["sources"]:
        urls.append(
            f"https://www.gumtree.co.za/s-houses-flats-for-sale/{location}"
        )

    if "facebook" in resolved["sources"]:
        urls.append(
            f"https://www.facebook.com/marketplace/{location}/propertyforsale"
        )

    return urls
