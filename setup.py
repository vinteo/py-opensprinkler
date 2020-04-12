"""pyopensprinkler setup script."""
from setuptools import setup

version = '0.1.1'

github_username = 'vinteo'
github_repository = 'py-opensprinkler'

github_path = '{}/{}'.format(github_username, github_repository)
github_url = 'https://github.com/{}'.format(github_path)

download_url = '{}/archive/{}.tar.gz'.format(github_url, version)
project_urls = {
    'Bug Reports': '{}/issues'.format(github_url)
}

setup(
    name='pyopensprinkler',
    version=version,
    author='Vincent Teo',
    author_email='vinteo@gmail.com',
    packages=['pyopensprinkler'],
    install_requires=['httplib2'],
    url=github_url,
    download_url=download_url,
    project_urls=project_urls,
    license='MIT',
    description='A Python module for the OpenSprinkler API.',
    platforms='Cross Platform',
)
