# BAH Capability Extension Starter Pack

This directory contains the starter template for building custom Space Situational Awareness (SSA) capability modules for VYOMNETRA.

## Quick Start
1. Subclass `CapabilityModule` from `vyomnetra.bah.framework`.
2. Implement `initialize()`, `execute()`, and `shutdown()`.
3. Register your module with `BAHModuleRegistry`.
4. Run `python runner.py` to execute.
