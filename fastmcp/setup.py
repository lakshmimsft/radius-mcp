from setuptools import setup, find_packages

setup(
    name="fastmcp",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "mcp[cli]>=1.6.0",
    ],
    py_modules=["fastmcp_server", "main"],
)