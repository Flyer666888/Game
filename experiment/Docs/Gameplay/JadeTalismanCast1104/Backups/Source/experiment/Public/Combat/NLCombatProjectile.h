#pragma once

#include "CoreMinimal.h"
#include "Combat/NLCombatTypes.h"
#include "GameFramework/Actor.h"
#include "NLCombatProjectile.generated.h"

class UNLAttackDefinition;
class USceneComponent;
class UStaticMeshComponent;
class UMaterialInterface;
class UPrimitiveComponent;
class UNLGuardComponent;
class USplineMeshComponent;
struct FCollisionQueryParams;

/** Straight projectile. Collision is swept explicitly, never from a mesh overlap event. */
UCLASS(Blueprintable)
class EXPERIMENT_API ANLCombatProjectile : public AActor
{
	GENERATED_BODY()

public:
	ANLCombatProjectile();
	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintCallable, Category="Combat|Projectile")
	bool InitializeProjectile(AActor* InSourceActor, UNLAttackDefinition* InAttackDefinition,
		FVector Direction, float SpeedCmPerSec, float RadiusCm, float LifetimeSeconds = 5.0f);

	/** Scheduled enemies share one attack ID with their director reservation. */
	UFUNCTION(BlueprintCallable, Category="Combat|Projectile")
	bool InitializeProjectileWithId(AActor* InSourceActor, UNLAttackDefinition* InAttackDefinition,
		FGuid InAttackInstanceId, FVector Direction, float SpeedCmPerSec, float RadiusCm, float LifetimeSeconds = 5.0f);

	void SetCombatPaused(bool bPaused);

	/** Called before initialization by the sword-qi launcher; other projectiles keep their sphere shape. */
	UFUNCTION(BlueprintCallable, Category="Combat|Projectile")
	void ConfigureHorizontalBladeQi();

	UFUNCTION(BlueprintPure, Category="Combat|Projectile")
	bool IsHorizontalBladeQi() const { return bHorizontalBladeQi; }

	static void SweepHorizontalBladeQi(UWorld* World, TArray<FHitResult>& OutHits,
		const FVector& Start, const FVector& End, const FQuat& Orientation, const FCollisionQueryParams& Params);

	/** Resolve the initial hand-to-muzzle path as real combat, so a close target cannot be skipped. */
	void AdvanceToLaunchMuzzle(const FVector& Position);

	UFUNCTION(BlueprintPure, Category="Combat|Projectile")
	AActor* GetSourceActor() const { return SourceActor.Get(); }

	UFUNCTION(BlueprintPure, Category="Combat|Projectile")
	FGuid GetAttackInstanceId() const { return AttackInstanceId; }

	UFUNCTION(BlueprintPure, Category="Combat|Projectile")
	int32 GetProjectileGeneration() const { return ProjectileGeneration; }

	UFUNCTION(BlueprintPure, Category="Combat|Projectile")
	int32 GetReflectionCount() const { return ReflectionCount; }

	/** Area skills may consume only an initialized, unpaused hostile projectile. Reflected player shots survive. */
	bool IsHostileToPlayer() const;

	// Encounter reset destroys old attacks. Generation increases on reflection;
	// a pool is not used yet and lifetime is never extended by reflection.
	static void DestroyWorldProjectiles(UWorld* World);
	static void DestroyEncounterProjectiles(AActor* EncounterActor);
	static void SetEncounterProjectilesPaused(AActor* EncounterActor, bool bPaused);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Projectile")
	TObjectPtr<USceneComponent> SceneRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Projectile")
	TObjectPtr<UStaticMeshComponent> Visual;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Projectile")
	TObjectPtr<UMaterialInterface> VisualMaterial;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Projectile", meta=(ClampMin="0"))
	int32 MaxReflectionCount = 2;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Projectile", meta=(ClampMin="0.0", Units="s"))
	float InitialSourceIgnoreSeconds = 0.1f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Projectile", meta=(ClampMin="0.0", Units="s"))
	float ReflectedShieldIgnoreSeconds = 0.08f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Projectile", meta=(ClampMin="1.0", Units="cm"))
	float ReflectionTargetRangeCm = 2200.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Projectile", meta=(ClampMin="1.0", ClampMax="89.0", Units="deg"))
	float ReflectionAimConeDegrees = 50.0f;

private:
	FNLCombatContact MakeContact(AActor* TargetActor, const FHitResult& Hit) const;
	void MoveSwept(const FVector& End);
	void ConsumeAt(const FVector& Position);
	bool ReflectFromGuard(AActor* NewSource, UNLGuardComponent* Guard,
		const FNLCombatResult& Result, const FVector& ContactPosition);
	FVector SelectReflectionDirection(AActor* PreferredTarget, const FVector& Origin,
		const FVector& GeometricDirection) const;
	void ApplySourcePresentation(bool bForceFactionMaterial);

	UPROPERTY(Transient)
	TObjectPtr<UNLAttackDefinition> AttackDefinition;

	UPROPERTY(Transient)
	TArray<TObjectPtr<USplineMeshComponent>> CrescentVisuals;

	TWeakObjectPtr<AActor> SourceActor;
	// Retained through reflection, even when the source/owner becomes the player.
	TWeakObjectPtr<AActor> OriginalEncounterOwner;
	TSet<TWeakObjectPtr<UPrimitiveComponent>> IgnoredBodyComponents;
	TSet<TWeakObjectPtr<UPrimitiveComponent>> IgnoredGuardComponents;
	TWeakObjectPtr<UPrimitiveComponent> TemporarilyIgnoredShield;
	FGuid AttackInstanceId;
	FVector Velocity = FVector::ZeroVector;
	float SweepRadiusCm = 7.0f;
	double ExpireGameTime = 0.0;
	double InitialSourceIgnoreUntilGameTime = 0.0;
	double ShieldIgnoreUntilGameTime = 0.0;
	int32 ProjectileGeneration = 0;
	int32 ReflectionCount = 0;
	bool bInitialized = false;
	bool bHorizontalBladeQi = false;
	bool bCombatPaused = false;
	double CombatPauseBeganGameTime = 0.0;
};
