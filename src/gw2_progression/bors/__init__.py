"""BORS — Business Decision Skill Kit.

Three-layer architecture:
  KPI Layer:   BusinessKPICalculator  — entity state → normalized KPI
  Risk Layer:  BusinessRiskModel     — KPI → risk assessment
  Decision:    DecisionEngine        — KPI + Risk → DecisionRecord (explainable)
  ValueGraph:                         — entity → KPI → decision propagation
"""
