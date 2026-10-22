from setuptools import setup
import re

requirements = []

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

version = ''
with open('vizium/__meta__.py') as f:
    version = re.search(
        r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', f.read(), re.MULTILINE).group(1)

readme = ""

with open("README.md") as f:
    readme = f.read()

setup(name="vizium",
      author="Yadiel A. Rodriguez",
      url="https://github.com/neokuze/Vizium",
      version=version,
      packages=["vizium"],
      license="AGPL-3.0",
      description="Async Python bots for Vizium",
      long_description=readme,
      long_description_content_type="text/markdown",
      install_requires=requirements,
      python_requires=">=3.9"
      )
