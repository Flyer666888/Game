#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "NLBladeComponent.generated.h"

class USceneComponent;
class UNLAttackDefinition;

// Emitted after the blade has sampled the current tracked pose, never from an
// input event or an actor tick reading last frame's velocity.
DECLARE_MULTICAST_DELEGATE_ThreeParams(FNLTrackedBladeMotionSample, const FGuid&, float, bool);
DECLARE_MULTICAST_DELEGATE(FNLBladeHistoryReset);

UENUM(BlueprintType)
enum class ENLBladeSwingState : uint8
{
	Ready,
	SwingActive,
	Recovery
};

// Tracks blade motion relative to a tracking origin, then sends contacts to the
// shared resolver. A desktop input may arm a swing; it never applies damage.
UCLASS(ClassGroup=(Combat), BlueprintType, Blueprintable, meta=(BlueprintSpawnableComponent))
class EXPERIMENT_API UNLBladeComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UNLBladeComponent();

	FNLTrackedBladeMotionSample OnTrackedMotionSample;
	FNLBladeHistoryReset OnHistoryReset;

	virtual void TickComponent(float DeltaTime, ELevelTick TickType,
		FActorComponentTickFunction* ThisTickFunction) override;

	UFUNCTION(BlueprintCallable, Category="Combat|Blade")
	void ConfigureBlade(USceneComponent* Weapon, USceneComponent* TrackingSpace);

	UFUNCTION(BlueprintCallable, Category="Combat|Blade")
	bool RequestDesktopSwing();

	UFUNCTION(BlueprintCallable, Category="Combat|Blade")
	void EndDesktopSwing();

	/** Animation/AI-owned damage window; first sample only establishes a baseline. */
	UFUNCTION(BlueprintCallable, Category="Combat|Blade")
	bool BeginAttackWindow();

	/** Preserve the attack identity allocated by the enemy director. */
	UFUNCTION(BlueprintCallable, Category="Combat|Blade")
	bool BeginAttackWindowWithId(FGuid AttackInstanceId);

	UFUNCTION(BlueprintCallable, Category="Combat|Blade")
	void EndAttackWindow();

	// Call when tracking is lost, the encounter resets, or pause changes.
	UFUNCTION(BlueprintCallable, Category="Combat|Blade")
	void ResetBladeHistory();

	/** Tracked swing mode stays enabled when input is lost; invalid poses never arm a swing. */
	UFUNCTION(BlueprintCallable, Category="Combat|Blade")
	void SetTrackedInputValid(bool bIsValid);

	/** Recenter, snap turn, or teleport: keep tracking validity but discard motion history. */
	UFUNCTION(BlueprintCallable, Category="Combat|Blade")
	void NotifyTrackingDiscontinuity();

	UFUNCTION(BlueprintPure, Category="Combat|Blade")
	bool IsReady() const;

	UFUNCTION(BlueprintPure, Category="Combat|Blade")
	ENLBladeSwingState GetSwingState() const { return SwingState; }

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Blade")
	TObjectPtr<UNLAttackDefinition> AttackDefinition;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Blade")
	bool bEnableTrackedSwing = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Blade", meta=(ClampMin="1.0", Units="cm/s"))
	float SpeedThresholdCmPerSec = 220.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Blade", meta=(ClampMin="0.0", Units="s"))
	float RecoverySeconds = 0.22f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Blade", meta=(ClampMin="0.1", Units="cm"))
	float SweepRadiusCm = 4.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Blade", meta=(ClampMin="0.001", Units="s"))
	float MaxSampleGapSeconds = 0.10f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Blade", meta=(ClampMin="1.0", Units="cm"))
	float MaxTrackingStepCm = 80.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Blade", meta=(ClampMin="0.0", Units="cm/s"))
	float MinSpeedCmPerSecToContinue = 70.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Blade", meta=(ClampMin="0.05", Units="s"))
	float MaxTrackedSwingSeconds = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Blade")
	FVector BladeRootLocal = FVector(0.0, 0.0, 9.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Blade")
	FVector BladeMidLocal = FVector(0.7, 0.0, 39.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Blade")
	FVector BladeTipLocal = FVector(4.3, 0.0, 70.972);

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Combat|Blade")
	float CurrentSpeedCmPerSec = 0.0f;

private:
	void BuildSamplePoints(TArray<FVector>& LocalPoints) const;
	void EnterRecovery(double Now);
	void SweepBlade(const TArray<FVector>& WorldPoints, const TArray<FVector>& SweepStartPoints,
		double SampleSeconds, double Now);
	void SweepSegment(const FVector& Start, const FVector& End,
		const FVector& BladeRoot, const FVector& Velocity, double Now);

	UPROPERTY(Transient)
	TObjectPtr<USceneComponent> WeaponComponent;

	UPROPERTY(Transient)
	TObjectPtr<USceneComponent> TrackingSpaceComponent;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Combat|Blade", meta=(AllowPrivateAccess="true"))
	ENLBladeSwingState SwingState = ENLBladeSwingState::Ready;

	TArray<FVector> PreviousWorldPoints;
	TArray<FVector> PreviousTrackingPoints;
	TSet<TWeakObjectPtr<AActor>> HitActors;
	FGuid SwingInstanceId;
	double PreviousSampleTime = 0.0;
	double RecoveryEndTime = 0.0;
	double TrackedSwingStartTime = 0.0;
	bool bHasPreviousSample = false;
	bool bDesktopSwingArmed = false;
	bool bExplicitAttackWindow = false;
	bool bTrackedInputValid = false;
	bool bTrackedSwingArmed = false;
};
