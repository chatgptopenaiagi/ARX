# Machine DNA
Machine DNA includes OS, CPU, memory, GPU, volumes, safe environment hints, SDK roots, and developer tools. Fixed version probes use `shell=False`, captured streams, hidden windows, and five-second timeouts. Missing data remains missing or unknown.

ARX 0.3 reuses Machine DNA `python_installations` observations to construct a Provider Graph. Provider identity includes normalized executable path/identity, version, provider kind, and discovery method, so equal versions at different locations remain separate. Provider availability and health do not determine which command resolves in a project execution context.

