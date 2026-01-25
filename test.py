resolver = BrandCategoryResolver()

print(resolver.resolve("Dell", "Laptop"))
print(resolver.resolve("Dell", None))
print(resolver.resolve("BrandKhongTonTai", "Laptop"))
