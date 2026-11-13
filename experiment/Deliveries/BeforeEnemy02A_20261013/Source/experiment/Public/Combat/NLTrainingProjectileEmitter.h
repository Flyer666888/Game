#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "NLTrainingProjectileEmitter.generated.h"

class UNLAttackDefinition;
class UNLCombatIdentityComponent;
class UNLCombatVitalsComponent;
class UCapsuleComponent;
class USceneComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

/** Explicitly enabled practice launcher; telegraphs and locks each shot before firing. */
UCLASS(Blueprintable)
class EXPERIMENT_API ANLTrainingProjectileEmitter : public AActor
{
	GENERATED_BODY()

public:
	ANLTrainingProjectileEmitter();
	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintCallable, Category="Combat|Training")
	void SetFiringEnabled(bool bEnabled);

	UFUNCTION(BlueprintCallable, Category="Combat|Training")
	bool ToggleFiring();

	UFUNCTION(BlueprintPure, Category="Combat|Training")
	bool IsFiringEnabled() const { return bFiringEnabled; }

	UFUNCTION(BlueprintPure, Category="Combat|Training")
	bool IsTelegraphing() const { return bTelegraphing; }

	UFUNCTION(BlueprintCallable, Category="Combat|Training")
	void ResetForEncounter();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Training")
	TObjectPtr<USceneComponent> SceneRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Training")
	TObjectPtr<UCapsuleComponent> Body;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Training")
	TObjectPtr<UStaticMeshComponent> Visual;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Training")
	TObjectPtr<UStaticMeshComponent> Muzzle;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Training")
	TObjectPtr<UTextRenderComponent> StatusText;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Training")
	TObjectPtr<UNLCombatIdentityComponent> CombatIdentity;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Training")
	TObjectPtr<UNLCombatVitalsComponent> Vitals;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Training")
	TObjectPtr<UNLAttackDefinition> AttackDefinition;

	/** Empty means player zero. Chest offset is relative to the pawn's actor origin. */
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Combat|Training")
	TObjectPtr<AActor> TargetActor;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Training")
	FVector TargetChestOffset = FVector(0.0, 0.0, 35.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Training", meta=(ClampMin="1.0", Units="cm/s"))
	float ProjectileSpeed = 550.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Training", meta=(ClampMin="0.1", Units="cm"))
	float ProjectileRadius = 7.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Training", meta=(ClampMin="0.1", Units="s"))
	float ProjectileLifetime = 6.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Training", meta=(ClampMin="0.05", Units="s"))
	float TelegraphSeconds = 0.6f;

	/** Time between shots, including the next telegraph. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Training", meta=(ClampMin="0.1", Units="s"))
	float FireIntervalSeconds = 1.5f;

protected:
	virtual void BeginPlay() override;

private:
	UFUNCTION()
	void HandleDied();
	AActor* ResolveTarget() const;
	bool CanAttackTarget(AActor* Target) const;
	void BeginTelegraph(AActor* Target, double Now);
	void FireProjectile(double Now);
	void UpdateStatus();

	FVector LockedTargetPosition = FVector::ZeroVector;
	double TelegraphFireTime = 0.0;
	double NextTelegraphTime = 0.0;
	bool bFiringEnabled = false;
	bool bTelegraphing = false;
};
