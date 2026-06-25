import type { ArmDto } from '@reports/shared';

export function ArmCard({ arm }: { arm: ArmDto }) {
  return (
    <section className="arm-card" aria-label={`Arm ${arm.label}`}>
      <h3>{arm.label}</h3>
      <p>{arm.modelName}</p>
      <small>{arm.kind}</small>
    </section>
  );
}
