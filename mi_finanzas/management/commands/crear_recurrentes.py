from django.core.management.base import BaseCommand
from django.utils import timezone
from mi_finanzas.models import Transaccion, TransaccionRecurrente 
# 🚨 ASUMIENDO que TransaccionRecurrente y Transaccion están en mi_finanzas/models.py
from datetime import timedelta 

class Command(BaseCommand):
    help = 'Crea transacciones regulares a partir de registros recurrentes si es su fecha.'

    def handle(self, *args, **options):
        
        # Usamos localdate() para comparaciones con campos DateField
        hoy = timezone.localdate()
        
        self.stdout.write(f"Iniciando verificación de transacciones recurrentes para la fecha: {hoy}")

        # 1. Buscar transacciones recurrentes cuyo 'proximo_pago' sea hoy o anterior
        recurrentes_a_crear = TransaccionRecurrente.objects.filter(
            proximo_pago__lte=hoy,
            esta_activa=True
        )

        creadas_count = 0
        
        # 2. Iterar, crear la transacción y actualizar la fecha de pago
        for recurrente in recurrentes_a_crear:
            try:
                # 🚨 CORRECCIÓN CLAVE: Asignar el campo 'usuario' 🚨
                nueva_transaccion = Transaccion.objects.create(
                    cuenta=recurrente.cuenta,
                    tipo=recurrente.tipo,
                    monto=recurrente.monto,
                    categoria=recurrente.categoria,
                    descripcion=recurrente.descripcion + ' (Recurrente)',
                    fecha=hoy,
                    # Obtiene el usuario a través de la relación de la cuenta
                    usuario=recurrente.cuenta.usuario 
                )
                
                # 3. Calcula la siguiente fecha de pago (debe estar en el modelo)
                # NOTA: Esto asume que el modelo TransaccionRecurrente tiene el método:
                # 'calcular_siguiente_fecha()'
                recurrente.proximo_pago = recurrente.calcular_siguiente_fecha() 
                recurrente.save()
                
                creadas_count += 1
                
            except Exception as e:
                # Muestra el error de forma clara
                self.stderr.write(self.style.ERROR(f"Error al procesar recurrente ID {recurrente.pk}: {e}"))

        self.stdout.write(self.style.SUCCESS(f'Proceso de recurrencia completado. Se crearon {creadas_count} transacciones.'))

