# Architecture

The dependency direction is `GUI / adapters / plugins -> Core`; Core does not import business plugins or external adapters. `CapabilityGateway` is the sole execution boundary and accepts only P01–P08. Source bytes are content-addressed by SHA-256 and verified on read. Evidence records retain project and source identifiers and expose an immutable payload.

