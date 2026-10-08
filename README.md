# RISC-V Fault Injection Across Simulators
A framework for running fault injection experiments on RISC-V across the following simulators :
- Qemu
- Renode
- gem5

## Requirements
The framework requires:
- Python 3
- RISC-V cross-compilation toolchain
- GDB with RISC-V support
- QEMU, gem5, and/or Renode depending on the experiments being run

Create and activate a virtual environment and install the required Python dependencies:
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYRENODE_PATH=/path/to/renode
```
## Running an Experiment
Experiments are defined using TOML configuration files

The command-line entry point is:
```
python run_experiment.py <experiment-config>
```
For example:
```
python run_experiment.py configs/experiments/register.toml
```
The CLI:

1) Loads the experiment configuration.
2) Creates the configured experiment.
3) Starts the experiment.
4) Runs the baseline and fault-injection trials.
5) Prints the resulting experiment outcome.

## Experiment Configuration
A configuration describes the experiment and its components, such as:

- simulator
- test program
- fault type
- fault parameters
- execution settings

Example:
```
name = "register_fault"

[program]
name = "register_test"
path = "programs/register/register_test.elf" 

[execution]
mode = "checkpoint"
inject_at = 0x80000008
end_at = 0x80000010
output_register = "x10"

[simulator]
name = "gem5"

[fault]
type = "register"
register = "x5"
value = "0x11111101"
```

## Fault Injection
The framework provides separate fault-injection strategies for different fault types.
### Register Faults
A register fault modifies the value of a selected CPU register during execution.
### Memory Faults
A memory fault modifies a value at a selected memory location.
### Program Counter Faults
A PC fault modifies the program counter to simulate control-flow corruption.