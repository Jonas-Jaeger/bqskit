"""This file tests the qasm2 language support in BQSKit."""
from __future__ import annotations

from unittest.mock import mock_open
from unittest.mock import patch

import pytest
from qiskit import QuantumCircuit

from bqskit.ext import qiskit_to_bqskit
from bqskit.ir.gates.circuitgate import CircuitGate
from bqskit.ir.gates.constant.cx import CNOTGate
from bqskit.ir.gates.measure import MeasurementPlaceholder
from bqskit.ir.gates.parameterized.u1 import U1Gate
from bqskit.ir.gates.parameterized.u2 import U2Gate
from bqskit.ir.lang.language import LangException
from bqskit.ir.lang.qasm2 import OPENQASM2Language


class TestGateDecl:
    def test_simple_gate_decl(self) -> None:
        input = """
            OPENQASM 2.0;
            include "qelib1.inc";
            qreg q[1];
            gate gate_x (p0) q0 {
                u2(p0, 3.5*p0) q0;
            }
            gate_x(1.2) q[0];
        """

        circuit = OPENQASM2Language().decode(input)
        assert circuit.num_qudits == 1
        assert circuit.num_operations == 1
        op = circuit[0, 0]
        assert isinstance(op.gate, CircuitGate)
        assert op.location == (0,)
        assert op.params == [1.2, 4.2]
        assert op.gate._circuit[0, 0].gate == U2Gate()
        assert op.gate._circuit[0, 0].location == (0,)

        qc = QuantumCircuit.from_qasm_str(input)
        bqskit_utry = circuit.get_unitary()
        qiskit_utry = qiskit_to_bqskit(qc).get_unitary()
        assert qiskit_utry.get_distance_from(bqskit_utry) < 1e-7

    def test_empty_gate_decl_1(self) -> None:
        input = """
            OPENQASM 2.0;
            include "qelib1.inc";
            qreg q[1];
            gate gate_x () q0 {
            }
            gate_x q[0];
        """

        circuit = OPENQASM2Language().decode(input)
        assert circuit.num_qudits == 1
        op = circuit[0, 0]
        assert isinstance(op.gate, CircuitGate)
        assert op.location == (0,)
        assert op.params == []

        qc = QuantumCircuit.from_qasm_str(input)
        bqskit_utry = circuit.get_unitary()
        qiskit_utry = qiskit_to_bqskit(qc).get_unitary()
        assert qiskit_utry.get_distance_from(bqskit_utry) < 1e-7

    def test_empty_gate_decl_2(self) -> None:
        input = """
            OPENQASM 2.0;
            include "qelib1.inc";
            qreg q[1];
            gate gate_x q0 {}
            gate_x q[0];
        """

        circuit = OPENQASM2Language().decode(input)
        assert circuit.num_qudits == 1
        op = circuit[0, 0]
        assert isinstance(op.gate, CircuitGate)
        assert op.location == (0,)
        assert op.params == []

        qc = QuantumCircuit.from_qasm_str(input)
        bqskit_utry = circuit.get_unitary()
        qiskit_utry = qiskit_to_bqskit(qc).get_unitary()
        assert qiskit_utry.get_distance_from(bqskit_utry) < 1e-7

    def test_gate_decl_qubit_mixup(self) -> None:
        input = """
            OPENQASM 2.0;
            include "qelib1.inc";
            qreg q[3];
            gate gate_x q0, q1, q2 {
                cx q2, q1;
                cx q0, q2;
                cx q1, q0;
                cx q2, q0;
            }
            gate_x q[1], q[2], q[0];
        """

        circuit = OPENQASM2Language().decode(input)
        assert circuit.num_qudits == 3
        op = circuit[0, 0]
        assert isinstance(op.gate, CircuitGate)
        assert op.location == (1, 2, 0)
        assert op.params == []

        subcircuit = op.gate._circuit
        assert subcircuit.num_qudits == 3
        assert subcircuit.num_cycles == 4
        assert subcircuit[0, 1].gate == CNOTGate()
        assert subcircuit[0, 1].location == (2, 1)
        assert subcircuit[1, 0].gate == CNOTGate()
        assert subcircuit[1, 0].location == (0, 2)
        assert subcircuit[2, 1].gate == CNOTGate()
        assert subcircuit[2, 1].location == (1, 0)
        assert subcircuit[3, 2].gate == CNOTGate()
        assert subcircuit[3, 2].location == (2, 0)

        qc = QuantumCircuit.from_qasm_str(input)
        bqskit_utry = circuit.get_unitary()
        qiskit_utry = qiskit_to_bqskit(qc).get_unitary()
        assert qiskit_utry.get_distance_from(bqskit_utry) < 1e-7

    def test_nested_gate_decl(self) -> None:
        input = """
            OPENQASM 2.0;
            include "qelib1.inc";
            qreg q[2];
            u1(0.1) q[0];
            gate gate_x (p0) q0 {
                u2(p0, 3.5*p0) q0;
            }
            gate gate_y (p0) q0, q1 {
                gate_x(p0) q0;
                u1(0.1) q0;
                gate_x(p0*2) q1;
            }
            gate_y(1.2) q[0], q[1];
        """

        circuit = OPENQASM2Language().decode(input)
        assert circuit.num_qudits == 2
        op = circuit[0, 0]
        assert op.gate == U1Gate()
        assert op.location == (0,)
        assert op.params == [0.1]

        op = circuit[1, 1]
        assert isinstance(op.gate, CircuitGate)
        assert op.location == (0, 1)
        assert op.params == [1.2, 4.2, 2.4, 8.4, 0.1]

        subcircuit = op.gate._circuit
        assert isinstance(subcircuit[0, 0].gate, CircuitGate)
        assert subcircuit[0, 0].gate._circuit[0, 0].gate == U2Gate()
        assert isinstance(subcircuit[0, 1].gate, CircuitGate)
        assert subcircuit[1, 0].gate == U1Gate()

        # Unable to verify this one with qiskit
        # https://github.com/Qiskit/qiskit-terra/issues/8558
        # qc = QuantumCircuit.from_qasm_str(input)
        # bqskit_utry = circuit.get_unitary()
        # qiskit_utry = qiskit_to_bqskit(qc).get_unitary()
        # assert qiskit_utry.get_distance_from(bqskit_utry) < 1e-7


class TestIncludeStatements:

    def test_include_no_exists(self) -> None:
        input = """
            OPENQASM 2.0;
            include "qelib1.inc";
            qreg q[2];
        """
        circuit = OPENQASM2Language().decode(input)
        assert circuit.num_qudits == 2
        assert circuit.num_operations == 0

    def test_include_simple(self) -> None:
        idata = """
            gate test(p) q { u1(p) q; }
        """
        input = """
            OPENQASM 2.0;
            include "test.inc";
            qreg q[1];
            test(0.1) q[0];
        """
        with patch('builtins.open', mock_open(read_data=idata)) as mock_file:
            with patch('os.path.isfile', lambda x: True):
                circuit = OPENQASM2Language().decode(input)
            mock_file.assert_called_with('test.inc')
        assert circuit.num_qudits == 1
        assert circuit.num_operations == 1
        gate_unitary = U1Gate().get_unitary([0.1])
        assert circuit.get_unitary().get_distance_from(gate_unitary) < 1e-7


class TestMeasure:
    def test_measure_single_bit(self) -> None:
        input = """
            OPENQASM 2.0;
            qreg q[1];
            creg c[1];
            measure q[0] -> c[0];
        """
        circuit = OPENQASM2Language().decode(input)
        expected = MeasurementPlaceholder([('c', 1)], {0: ('c', 0)})
        assert circuit[0, 0].gate == expected

    def test_measure_register_1(self) -> None:
        input = """
            OPENQASM 2.0;
            qreg q[1];
            creg c[1];
            measure q -> c;
        """
        circuit = OPENQASM2Language().decode(input)
        expected = MeasurementPlaceholder([('c', 1)], {0: ('c', 0)})
        assert circuit[0, 0].gate == expected

    def test_measure_register_2(self) -> None:
        input = """
            OPENQASM 2.0;
            qreg q[2];
            creg c[2];
            measure q -> c;
        """
        circuit = OPENQASM2Language().decode(input)
        measurements = {0: ('c', 0), 1: ('c', 1)}
        expected = MeasurementPlaceholder([('c', 2)], measurements)
        assert circuit[0, 0].gate == expected

    def test_measure_register_invalid_size(self) -> None:
        input = """
            OPENQASM 2.0;
            qreg q[2];
            creg c[1];
            measure q -> c;
        """
        with pytest.raises(LangException):
            circuit = OPENQASM2Language().decode(input)  # noqa
