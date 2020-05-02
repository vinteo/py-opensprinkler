"""pyopensprinkler setup script."""
from setuptools import setup

version = "0.3.0"

github_username = "vinteo"
github_repository = "py-opensprinkler"

github_path = f"{github_username}/{github_repository}"
github_url = f"https://github.com/{github_path}"

download_url = f"{github_url}/archive/{version}.tar.gz"
project_urls = {"Bug Reports": f"{github_url}/issues"}

setup(
    name="pyopensprinkler",
    version=version,
    author="Vincent Teo",
    author_email="vinteo@gmail.com",
    packages=["pyopensprinkler"],
    install_requires=["httplib2==0.10.3", "cachetools==4.1.0"],
    url=github_url,
    download_url=download_url,
    project_urls=project_urls,
    license="MIT",
    description="A Python module for the OpenSprinkler API.",
    platforms="Cross Platform",
)
