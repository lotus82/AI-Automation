"""Совместимость импорта: регистрация пациента МИС через MAX перенесена в ``mis_max_bot_patient_reg_flow``."""

from src.infrastructure.mis_max_bot_patient_reg_flow import try_max_bot_mis_patient_registration_flow

try_max_bot_mis_patient_start_registration = try_max_bot_mis_patient_registration_flow

__all__ = ["try_max_bot_mis_patient_start_registration", "try_max_bot_mis_patient_registration_flow"]
