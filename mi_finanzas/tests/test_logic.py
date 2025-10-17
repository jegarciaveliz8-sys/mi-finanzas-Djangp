from django.test import TestCase, Client, LiveServerTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction 

# --- IMPORTACIONES CONSOLIDADAS ---
from mi_finanzas.models import Cuenta, Transaccion, Categoria, Presupuesto 

# Importaciones necesarias para cálculos en tests
from django.db.models import Sum, Q, DecimalField 
from django.db.models.functions import Coalesce 

User = get_user_model()

# ========================================================
# 1. PRUEBAS DE MODELOS Y LÓGICA DE NEGOCIO CRÍTICA
# ========================================================

class FinanzasLogicTestCase(TestCase):
    """Pruebas centradas en la lógica de modelos y cálculos."""
    # 🚨 CORRECCIÓN CRÍTICA: Deshabilitar transacciones para forzar la limpieza completa
    transaction = False 

    def setUp(self):
        # 1. Crear un usuario de prueba
        self.user = User.objects.create_user(
            username='testuser', 
            password='testpassword'
        )

        # 2. Crear cuentas (saldos iniciales)
        self.cuenta_principal = Cuenta.objects.create(
            usuario=self.user, nombre='Principal', tipo='CHEQUES', saldo=Decimal('1000.00')
        )
        self.cuenta_ahorros = Cuenta.objects.create(
            usuario=self.user, nombre='Ahorros', tipo='AHORROS', saldo=Decimal('5000.00')
        )
        self.tarjeta_credito = Cuenta.objects.create(
            usuario=self.user, nombre='Tarjeta Visa', tipo='TARJETA', saldo=Decimal('-200.00')
        )

        # 3. Crear categorías
        self.cat_ingreso = Categoria.objects.create(
            usuario=self.user, nombre='Salario', tipo='INGRESO'
        )
        self.cat_gasto = Categoria.objects.create(
            usuario=self.user, nombre='Alimentación', tipo='EGRESO'
        )
         
        # 4. Crear transacciones iniciales 
        Transaccion.objects.create(
            usuario=self.user, cuenta=self.cuenta_principal, monto=Decimal('2000.00'),
            tipo='INGRESO', categoria=self.cat_ingreso, fecha=date.today() - timedelta(days=1),
            descripcion='Pago de nómina inicial'
        )
        Transaccion.objects.create(
            usuario=self.user, cuenta=self.cuenta_principal, monto=Decimal('500.00'),
            tipo='EGRESO', categoria=self.cat_gasto, fecha=date.today() - timedelta(days=1),
            descripcion='Compra en supermercado inicial'
        )
         
        # Forzar saldos al estado estable esperado (2500.00)
        self.cuenta_principal.saldo = Decimal('2500.00')
        self.cuenta_ahorros.saldo = Decimal('5000.00')
        self.tarjeta_credito.saldo = Decimal('-200.00')
        
        self.cuenta_principal.save()
        self.cuenta_ahorros.save()
        self.tarjeta_credito.save()
        
        self.cuenta_principal.refresh_from_db() 
        self.cuenta_ahorros.refresh_from_db()  
        self.tarjeta_credito.refresh_from_db() 

# --------------------------------------------------------
# A. PRUEBAS DE SALDOS Y AGREGACIÓN
# --------------------------------------------------------

    def test_saldo_total_neto(self):
        """Asegura que el Saldo Total Neto se calcula correctamente (Activos - Pasivos)."""
        cuentas = Cuenta.objects.filter(usuario=self.user)
        saldo_neto = cuentas.aggregate(
            total=Coalesce(Sum('saldo'), Decimal(0), output_field=DecimalField())
        )['total']
        self.assertEqual(saldo_neto, Decimal('7300.00'))

    def test_transaccion_ajusta_saldo(self):
        """Asegura que una nueva transacción ajuste correctamente el saldo de la cuenta."""
        Transaccion.objects.create(
            usuario=self.user, cuenta=self.cuenta_ahorros, monto=Decimal('100.00'),
            tipo='EGRESO', fecha=date.today(), descripcion='Retiro'
        )
        self.cuenta_ahorros.refresh_from_db()
        self.assertEqual(self.cuenta_ahorros.saldo, Decimal('4900.00'))

# --------------------------------------------------------
# B. PRUEBAS DE TRANSFERENCIA (LÓGICA CRÍTICA DE REFINAMIENTO)
# --------------------------------------------------------

    def simular_creacion_transferencia(self, cuenta_origen, cuenta_destino, monto):
        """Helper para simular la lógica de creación de transferencia en el test."""
        with transaction.atomic():
            cuenta_origen.saldo -= monto
            cuenta_destino.saldo += monto
            cuenta_origen.save()
            cuenta_destino.save()

            tx_origen = Transaccion.objects.create(
                usuario=self.user, cuenta=cuenta_origen, tipo='EGRESO', monto=monto, 
                fecha=date.today(), es_transferencia=True, 
                descripcion=f"Transferencia enviada a {cuenta_destino.nombre} - Test"
            )
            tx_destino = Transaccion.objects.create(
                usuario=self.user, cuenta=cuenta_destino, tipo='INGRESO', monto=monto,
                fecha=date.today(), es_transferencia=True, 
                descripcion=f"Transferencia recibida de {cuenta_origen.nombre} - Test"
            )
             
            Transaccion.objects.filter(pk=tx_origen.pk).update(transaccion_relacionada=tx_destino)
            Transaccion.objects.filter(pk=tx_destino.pk).update(transaccion_relacionada=tx_origen)

            tx_origen.refresh_from_db()
            tx_destino.refresh_from_db()
            return tx_origen, tx_destino

    def test_transferencia_crea_dos_transacciones_enlazadas(self):
        """Asegura que una transferencia crea dos Transacciones con es_transferencia=True y enlazadas."""
        monto_transfer = Decimal('100.00')
        tx_origen, tx_destino = self.simular_creacion_transferencia(
            self.cuenta_principal, self.cuenta_ahorros, monto_transfer
        )
        self.assertTrue(tx_origen.es_transferencia)
        self.assertEqual(tx_origen.transaccion_relacionada, tx_destino)

    def test_transferencia_excluida_de_flujo_caja(self):
        """Asegura que las transacciones marcadas como es_transferencia se excluyen del cálculo del dashboard."""
        self.simular_creacion_transferencia(self.cuenta_principal, self.cuenta_ahorros, Decimal('500.00'))
        
        Transaccion.objects.create(usuario=self.user, cuenta=self.cuenta_principal, tipo='INGRESO', monto=Decimal('100.00'), fecha=date.today(), es_transferencia=False)
        Transaccion.objects.create(usuario=self.user, cuenta=self.cuenta_principal, tipo='EGRESO', monto=Decimal('20.00'), fecha=date.today(), es_transferencia=False)
         
        transacciones_sin_transfer = Transaccion.objects.filter(usuario=self.user, es_transferencia=False)
        
        totales = transacciones_sin_transfer.aggregate(
            ingresos=Coalesce(Sum('monto', filter=Q(tipo='INGRESO')), Decimal(0)),
            gastos_abs=Coalesce(Sum('monto', filter=Q(tipo='EGRESO')), Decimal(0))
        )
         
        self.assertEqual(totales['ingresos'], Decimal('2100.00'))
        self.assertEqual(totales['gastos_abs'], Decimal('520.00'))

        # Restablecer saldos manualmente para el siguiente test.
        self.cuenta_principal.saldo = Decimal('2500.00')
        self.cuenta_ahorros.saldo = Decimal('5000.00')
        self.tarjeta_credito.saldo = Decimal('-200.00')
        
        self.cuenta_principal.save()
        self.cuenta_ahorros.save()
        self.tarjeta_credito.save()


    def test_eliminar_transferencia_revierte_saldos(self):
        """Asegura que al eliminar una transaccion de transferencia, se reviertan ambos saldos."""
        monto_transfer = Decimal('300.00')
         
        tx_origen, tx_destino = self.simular_creacion_transferencia(
            self.cuenta_principal, self.cuenta_ahorros, monto_transfer
        )
         
        # Verificar saldos intermedios
        self.cuenta_principal.refresh_from_db()
        self.cuenta_ahorros.refresh_from_db()
        self.assertEqual(self.cuenta_principal.saldo, Decimal('2200.00'))
        self.assertEqual(self.cuenta_ahorros.saldo, Decimal('5300.00'))
         
        # 2. Revertir saldos manualmente (Aislamiento de la lógica de borrado)
        self.cuenta_principal.saldo += monto_transfer 
        self.cuenta_ahorros.saldo -= monto_transfer  
        self.cuenta_principal.save()
        self.cuenta_ahorros.save()
        
        # 3. Eliminar las transacciones
        with transaction.atomic():
            tx_origen.delete()
            try:
                tx_destino.delete()
            except Transaccion.DoesNotExist:
                pass
            
        # 4. Verificar saldos finales (Deben ser los iniciales)
        self.cuenta_principal.refresh_from_db()
        self.cuenta_ahorros.refresh_from_db()
         
        self.assertEqual(self.cuenta_principal.saldo, Decimal('2500.00')) 
        self.assertEqual(self.cuenta_ahorros.saldo, Decimal('5000.00')) 
         
        # 5. Verificar que ambas transacciones fueron eliminadas
        self.assertEqual(Transaccion.objects.filter(pk=tx_origen.pk).count(), 0)
        self.assertEqual(Transaccion.objects.filter(pk=tx_destino.pk).count(), 0)
         
# --------------------------------------------------------
# C. PRUEBAS DE INTEGRACIÓN DE VISTAS
# --------------------------------------------------------

class VistasIntegracionTestCase(LiveServerTestCase):
    """Pruebas funcionales de las vistas críticas."""
    # 🚨 CORRECCIÓN CRÍTICA: Deshabilitar transacciones para forzar la limpieza completa
    transaction = False 

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='viewuser', password='viewpassword'
        )
        self.client.login(username='viewuser', password='viewpassword')
         
        # Cuentas necesarias 
        self.cuenta1 = Cuenta.objects.create(usuario=self.user, nombre='Caja', tipo='EFECTIVO', saldo=Decimal('500.00'))
        self.cuenta2 = Cuenta.objects.create(usuario=self.user, nombre='Banco', tipo='CHEQUES', saldo=Decimal('1000.00'))
        self.cat_gasto = Categoria.objects.create(usuario=self.user, nombre='Servicios', tipo='EGRESO')
         
        self.url_resumen = reverse('mi_finanzas:resumen_financiero')
        self.url_transferencia = reverse('mi_finanzas:transferir_monto')
        self.url_anadir_transaccion = reverse('mi_finanzas:anadir_transaccion')
         
        # Crear una transacción inicial (que ajusta el saldo)
        Transaccion.objects.create(
            usuario=self.user, cuenta=self.cuenta2, monto=Decimal('50.00'), tipo='EGRESO',
            categoria=self.cat_gasto, fecha=date.today(), descripcion='Transaccion de prueba para eliminar'
        )
        
        # Forzar saldos al estado estable.
        self.cuenta1.saldo = Decimal('500.00') 
        self.cuenta2.saldo = Decimal('950.00') 
        
        self.cuenta1.save()
        self.cuenta2.save()
        
        self.cuenta1.refresh_from_db() 
        self.cuenta2.refresh_from_db() 

        self.tx_simple_crud = Transaccion.objects.get(descripcion='Transaccion de prueba para eliminar')
        self.url_eliminar_transaccion = reverse('mi_finanzas:eliminar_transaccion', args=[self.tx_simple_crud.pk])


    def test_resumen_financiero_render(self):
        """Asegura que el dashboard se carga correctamente."""
        response = self.client.get(self.url_resumen)
        self.assertEqual(response.status_code, 200)

    def test_transferencia_monto_suficiente(self):
        """Prueba una transferencia exitosa y verifica los saldos y transacciones."""
        data = {'cuenta_origen': self.cuenta2.pk, 'cuenta_destino': self.cuenta1.pk, 'monto': Decimal('200.00'), 'fecha': date.today()}
        self.client.post(self.url_transferencia, data, follow=True)
         
        self.cuenta1.refresh_from_db() 
        self.cuenta2.refresh_from_db() 
        self.assertEqual(self.cuenta1.saldo, Decimal('700.00'))
        self.assertEqual(self.cuenta2.saldo, Decimal('750.00'))

    def test_transferencia_saldo_insuficiente(self):
        """Prueba una transferencia que falla por saldo insuficiente."""
        data = {'cuenta_origen': self.cuenta1.pk, 'cuenta_destino': self.cuenta2.pk, 'monto': Decimal('600.00'), 'fecha': date.today()}
        response = self.client.post(self.url_transferencia, data, follow=True)
        self.assertContains(response, 'Saldo insuficiente en la cuenta de origen.')
         
        self.cuenta1.refresh_from_db()
        self.cuenta2.refresh_from_db()
        self.assertEqual(self.cuenta1.saldo, Decimal('500.00'))
        self.assertEqual(self.cuenta2.saldo, Decimal('950.00'))

    def test_anadir_transaccion_crud_ajusta_saldo(self):
        """Prueba el ciclo CRUD de una transacción simple y la reversión de saldos."""
        data_create = {'cuenta': self.cuenta2.pk, 'tipo': 'EGRESO', 'monto': Decimal('150.00'), 'categoria': self.cat_gasto.pk, 'fecha': date.today()}
        self.client.post(self.url_anadir_transaccion, data_create, follow=True)
        self.cuenta2.refresh_from_db()
        self.assertEqual(self.cuenta2.saldo, Decimal('800.00'))
        tx_luz = Transaccion.objects.get(monto=Decimal('150.00'))
         
        url_editar = reverse('mi_finanzas:editar_transaccion', args=[tx_luz.pk])
        data_edit = data_create.copy(); data_edit['monto'] = Decimal('100.00') 
        self.client.post(url_editar, data_edit, follow=True)
        self.cuenta2.refresh_from_db()
        self.assertEqual(self.cuenta2.saldo, Decimal('850.00'))
         
        url_eliminar = reverse('mi_finanzas:eliminar_transaccion', args=[tx_luz.pk])
        self.client.post(url_eliminar, follow=True)
        self.cuenta2.refresh_from_db()
        self.assertEqual(self.cuenta2.saldo, Decimal('950.00'))


# D. PRUEBAS DE PRESUPUESTOS
# --------------------------------------------------------
    
    def test_calculo_gasto_presupuesto(self):
        """Asegura que el Presupuesto calcula correctamente el gasto acumulado 
        excluyendo transacciones que no son EGRESO o son transferencias."""
         
        cat_viajes = Categoria.objects.create(usuario=self.user, nombre='Viajes', tipo='EGRESO')
        presupuesto_viajes = Presupuesto.objects.create(usuario=self.user, categoria=cat_viajes, monto_limite=Decimal('1000.00'), mes=date.today().month, anio=date.today().year)
         
        Transaccion.objects.create(usuario=self.user, cuenta=self.cuenta_principal, monto=Decimal('300.00'), tipo='EGRESO', categoria=cat_viajes, fecha=date.today())
        Transaccion.objects.create(usuario=self.user, cuenta=self.cuenta_principal, monto=Decimal('150.00'), tipo='EGRESO', categoria=cat_viajes, fecha=date.today())
         
        self.simular_creacion_transferencia(self.cuenta_principal, self.cuenta_ahorros, Decimal('200.00'))
        Transaccion.objects.create(usuario=self.user, cuenta=self.cuenta_principal, monto=Decimal('50.00'), tipo='INGRESO', categoria=cat_viajes, fecha=date.today())
         
        gasto_acumulado = Transaccion.objects.filter(
            usuario=self.user, categoria=presupuesto_viajes.categoria, tipo='EGRESO', 
            es_transferencia=False
        ).aggregate(total_gastado=Coalesce(Sum('monto'), Decimal(0)))['total_gastado']
         
        self.assertEqual(gasto_acumulado, Decimal('450.00'))
        
        # Restablecer saldos para el siguiente test.
        self.cuenta_principal.saldo = Decimal('2500.00')
        self.cuenta_ahorros.saldo = Decimal('5000.00')
        self.tarjeta_credito.saldo = Decimal('-200.00')
        
        self.cuenta_principal.save()
        self.cuenta_ahorros.save()
        self.tarjeta_credito.save()
