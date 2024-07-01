# Contributing to meshtastic-metrics-exporter

We welcome contributions to the meshtastic-metrics-exporter project! This document outlines some guidelines to help you get started.

## Getting Started

1. Fork the repository and clone it locally.
2. Set up the project according to the instructions in the README.md file.

## Testing Locally

Before submitting a pull request, please ensure that you:

1. Run the project locally using Docker Compose:
   ```bash
   docker-compose up --build
   ```
2. Test with various packet types to ensure that no packets break the code.
3. Verify that all metrics are being exported correctly to Prometheus.

## Adding Tests

We highly encourage adding tests for new features or bug fixes. If you're adding new functionality, please include relevant tests. This helps maintain the stability and reliability of the project.

## Submitting Changes

1. Create a new branch for your changes.
2. Make your changes and commit them with clear, descriptive commit messages.
3. Push your changes to your fork.
4. Submit a pull request to the main repository.

## Reporting Issues

If you find any bugs or have feature suggestions, please open an issue on the GitHub repository. Provide as much detail as possible, including steps to reproduce the issue if applicable.

Thank you for contributing to meshtastic-metrics-exporter!
