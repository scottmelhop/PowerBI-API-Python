import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("requirements.txt") as fh:
    install_requires = fh.read().splitlines()

setuptools.setup(
    name="pbiapi",
    version="0.2.4",
    author="Scott Melhop",
    author_email="scott.melhop@gmail.com",
    description="A Python library for working with the Power BI API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/scottmelhop/PowerBI-API-Python",
    packages=setuptools.find_packages(),
    install_requires=install_requires,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
