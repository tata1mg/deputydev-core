from setuptools import find_packages, setup

with open("requirements/base.txt") as f:
    base_requirements = f.read().splitlines()

dependency_links = []

setup(
    name="deputydev-core",
    version="1.1.0",
    author="1mg",
    author_email="devops@1mg.com",
    description="Core logic of deputydev",
    packages=find_packages(exclude="requirements"),
    install_requires=base_requirements,
)
