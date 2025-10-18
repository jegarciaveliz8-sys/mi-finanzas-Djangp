# mi_finanzas/tests/test_consolidado.py

from django.test import TestCase, Client 
# ... todas tus demás importaciones (models, user, decimal, etc.) ...

# Clase con la lógica de modelos
class FinanzasLogicTestCase(TestCase):
    def setUp(self):
        # ... 
        # CORRECCIÓN AQUÍ: saldo= en lugar de balance=
        self.cuenta_principal = Cuenta.objects.create(
            usuario=self.user, nombre='Principal', tipo='CHEQUES', saldo=Decimal('1000.00')
        )
        # ...
    # ... todos tus métodos test_saldo_total_neto, etc. ...


# Clase con la lógica de vistas
class PanelDeControlTest(TestCase):
    def setUp(self):
        # ...
        # CORRECCIÓN AQUÍ: saldo= en lugar de balance=
        self.cuenta1 = Cuenta.objects.create(usuario=self.user, nombre='Caja', tipo='EFECTIVO', saldo=Decimal('500.00'))
        # ...
    # ... todos tus métodos test_panel_de_control_calculates_correct_summary, etc. ...

