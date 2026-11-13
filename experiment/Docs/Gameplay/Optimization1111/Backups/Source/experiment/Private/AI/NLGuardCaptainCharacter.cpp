#include "AI/NLGuardCaptainCharacter.h"

#include "AI/NLEnemyBrainComponent.h"
#include "Animation/AnimSequenceBase.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatResolverSubsystem.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Combat/NLGuardComponent.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"

ANLGuardCaptainCharacter::ANLGuardCaptainCharacter()
{
    GetEnemyBrain()->Role = ENLEnemyRole::GuardCaptain;
    // Scale every authored sword stage together, preserving the notify/brain overlap.
    GetEnemyBrain()->TelegraphSeconds = 1.2f;
    GetEnemyBrain()->AttackSeconds = 0.345f;
    GetEnemyBrain()->RecoverSeconds = 1.955f;
    GetEnemyBrain()->MinimumSlotWaitSeconds = 1.4f;
    Vitals->MaxGuard = 40.0f;
    Vitals->Guard = 40.0f;

    CaptainGuard = CreateDefaultSubobject<UNLGuardComponent>(TEXT("CaptainGuard"));
    CaptainGuard->MaintenanceCostPerSecond = 0.0f;
    CaptainGuard->MeleeBlockGuardCost = 20.0f;
    CaptainGuard->BlockGuardCost = 20.0f;
    CaptainGuard->PerfectWindowSeconds = 0.0f;
    CaptainGuard->RecoveryDelaySeconds = 0.0f;
    CaptainGuard->RecoveryPerSecond = 40.0f;
    CaptainGuard->GuardBreakSeconds = 1.2f;
    CaptainGuard->MinimumFacingDot = 0.35f;
    CaptainGuard->ContactPadding = 3.0f;

    CaptainGuardVisual = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("CaptainGuardVisual"));
    CaptainGuardVisual->SetupAttachment(GetCapsuleComponent());
    CaptainGuardVisual->SetRelativeLocation(FVector(42.0f, 0.0f, 8.0f));
    CaptainGuardVisual->SetRelativeRotation(FRotator(90.0f, 0.0f, 0.0f));
    CaptainGuardVisual->SetRelativeScale3D(FVector(0.70f, 0.70f, 0.035f));
    CaptainGuardVisual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    CaptainGuardVisual->SetCanEverAffectNavigation(false);
    CaptainGuardVisual->SetCastShadow(false);
    CaptainGuardVisual->SetHiddenInGame(true);

    // Outward +X matches the actor's facing; the thin ward leaves legs/back exposed.
    CaptainGuardCollision = CreateDefaultSubobject<UBoxComponent>(TEXT("CaptainGuardCollision"));
    CaptainGuardCollision->SetupAttachment(GetCapsuleComponent());
    CaptainGuardCollision->SetRelativeLocation(FVector(42.0f, 0.0f, 8.0f));
    CaptainGuardCollision->SetBoxExtent(FVector(7.0f, 35.0f, 35.0f));
    CaptainGuardCollision->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    CaptainGuardCollision->SetCanEverAffectNavigation(false);
    CaptainGuardCollision->SetHiddenInGame(true);
    CaptainGuard->GuardCollision = CaptainGuardCollision;
    CaptainGuard->GuardVisual = CaptainGuardVisual;
    Tags.Add(TEXT("NL_GuardCaptainEnemy"));
}

void ANLGuardCaptainCharacter::BeginPlay()
{
    Super::BeginPlay();
    CaptainGuardVisual->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,
        TEXT("/Engine/BasicShapes/Cylinder.Cylinder")));
    if (!GuardFieldMaterial)
        GuardFieldMaterial = LoadObject<UMaterialInterface>(nullptr,
            TEXT("/Game/ReversedScale/Combat/Materials/M_GuardCaptainWard.M_GuardCaptainWard"));
    if (GuardFieldMaterial)
    {
        GuardFieldInstance = UMaterialInstanceDynamic::Create(GuardFieldMaterial, this);
        CaptainGuardVisual->SetMaterial(0, GuardFieldInstance);
    }
    CaptainGuard->GuardBreakSeconds = FMath::Clamp(FMath::IsFinite(GuardBreakExposureSeconds)
        ? GuardBreakExposureSeconds : 1.2f, 0.2f, 5.0f);
    CaptainGuard->ConfigureGuard(CaptainGuardCollision, CaptainGuardVisual);
    CaptainGuard->OnGuardBroken.AddDynamic(this, &ANLGuardCaptainCharacter::HandleCaptainGuardBroken);
    GetEnemyBrain()->OnStateChanged.AddDynamic(this, &ANLGuardCaptainCharacter::HandleCaptainStateChanged);
    if (UNLCombatResolverSubsystem* Resolver = GetWorld()->GetSubsystem<UNLCombatResolverSubsystem>())
        Resolver->OnCombatResult.AddDynamic(this, &ANLGuardCaptainCharacter::HandleCaptainCombatResult);
    UpdateCaptainDefense();
    UpdateCaptainStatus();
}

void ANLGuardCaptainCharacter::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    CaptainGuard->SetGuardHeld(false);
    CaptainGuard->OnGuardBroken.RemoveDynamic(this, &ANLGuardCaptainCharacter::HandleCaptainGuardBroken);
    GetEnemyBrain()->OnStateChanged.RemoveDynamic(this, &ANLGuardCaptainCharacter::HandleCaptainStateChanged);
    if (UWorld* World = GetWorld())
        if (UNLCombatResolverSubsystem* Resolver = World->GetSubsystem<UNLCombatResolverSubsystem>())
            Resolver->OnCombatResult.RemoveDynamic(this, &ANLGuardCaptainCharacter::HandleCaptainCombatResult);
    Super::EndPlay(EndPlayReason);
}

void ANLGuardCaptainCharacter::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!GetWorld() || GetWorld()->IsPaused() || NativeIsLabPaused()) return;
    const float Step = FMath::IsFinite(DeltaSeconds) ? FMath::Max(0.0f, DeltaSeconds) : 0.0f;
    CounterWindowRemaining = FMath::Max(0.0f, CounterWindowRemaining - Step);
    BlockFlashRemaining = FMath::Max(0.0f, BlockFlashRemaining - Step);
    UpdateCaptainDefense();
    UpdateCaptainStatus();
}

void ANLGuardCaptainCharacter::SetCombatEnabled(bool bEnabled)
{
    if (!bEnabled) CaptainGuard->SetGuardHeld(false);
    Super::SetCombatEnabled(bEnabled);
    UpdateCaptainDefense();
    UpdateCaptainStatus();
}

void ANLGuardCaptainCharacter::SetLabPaused(bool bPaused)
{
    const bool bWasPaused = NativeIsLabPaused();
    CaptainGuard->SetCombatPaused(bPaused);
    Super::SetLabPaused(bPaused);
    if (bWasPaused && !bPaused && IsCombatEnabled() && CounterWindowRemaining > 0.0f)
        GetEnemyBrain()->ApplyStagger(CounterWindowRemaining);
    UpdateCaptainDefense();
    UpdateCaptainStatus();
}

void ANLGuardCaptainCharacter::ResetForEncounter()
{
    CounterWindowRemaining = BlockFlashRemaining = 0.0f;
    CaptainGuard->ResetGuard();
    Super::ResetForEncounter();
    CaptainGuard->SetGuardHeld(false);
    UpdateCaptainStatus();
}

void ANLGuardCaptainCharacter::HandleCaptainStateChanged(AActor* Enemy,
    ENLEnemyState PreviousState, ENLEnemyState NewState)
{
    if (NewState == ENLEnemyState::Dead || NewState == ENLEnemyState::Despawn)
        CounterWindowRemaining = BlockFlashRemaining = 0.0f;
    UpdateCaptainDefense();
    UpdateCaptainStatus();
}

void ANLGuardCaptainCharacter::HandleCaptainGuardBroken()
{
    if (!IsCombatEnabled() || Vitals->IsDead() || NativeIsLabPaused()) return;
    CounterWindowRemaining = FMath::Clamp(FMath::IsFinite(GuardBreakExposureSeconds)
        ? GuardBreakExposureSeconds : 1.2f, 0.2f, 5.0f);
    CaptainGuard->SetGuardHeld(false);
    // Existing brain cancellation closes the blade and releases the same Director GUID.
    GetEnemyBrain()->ApplyStagger(CounterWindowRemaining);
    UpdateCaptainStatus();
}

void ANLGuardCaptainCharacter::HandleCaptainCombatResult(const FNLCombatResult& Result)
{
    if (!CombatIdentity || Result.TargetRuntimeId != CombatIdentity->GetRuntimeId()) return;
    if (Result.Outcome == ENLCombatOutcome::Blocked)
        BlockFlashRemaining = 0.18f;
    // A health hit normally uses the existing 0.8s reaction; do not shorten a break opening.
    if (Result.Outcome == ENLCombatOutcome::Hit && CounterWindowRemaining > 0.0f
        && IsCombatEnabled() && !NativeIsLabPaused())
        GetEnemyBrain()->ApplyStagger(FMath::Max(CounterWindowRemaining,
            HitReactionAnimation ? HitReactionAnimation->GetPlayLength() : 0.8f));
    UpdateCaptainDefense();
    UpdateCaptainStatus();
}

void ANLGuardCaptainCharacter::UpdateCaptainDefense()
{
    const ENLEnemyState State = GetEnemyBrain()->GetState();
    const bool bDefensiveState = State == ENLEnemyState::Approach || State == ENLEnemyState::WaitForSlot;
    const bool bCanRaise = IsCombatEnabled() && !NativeIsLabPaused() && bDefensiveState
        && CounterWindowRemaining <= 0.0f && !CaptainGuard->IsGuardBroken();
    // Never repeatedly re-break an empty guard while its off-state recovery is running.
    const bool bEnoughToRaise = CaptainGuard->IsGuardActive()
        || CaptainGuard->GetGuard() >= CaptainGuard->MeleeBlockGuardCost;
    CaptainGuard->SetGuardHeld(bCanRaise && bEnoughToRaise);
    if (GuardFieldInstance)
        GuardFieldInstance->SetScalarParameterValue(TEXT("GlowStrength"),
            0.7f + 2.0f * FMath::Clamp(BlockFlashRemaining / 0.18f, 0.0f, 1.0f));
}

void ANLGuardCaptainCharacter::UpdateCaptainStatus()
{
    if (!StatusText || !Vitals) return;
    const ENLEnemyState State = GetEnemyBrain()->GetState();
    FString Cue;
    FColor Color(120, 220, 245);
    if (Vitals->IsDead()) { Cue = TEXT("CAPTAIN DEFEATED"); Color = FColor(150,210,160); }
    else if (NativeIsLabPaused()) Cue = TEXT("CAPTAIN PAUSED");
    else if (!IsCombatEnabled()) Cue = TEXT("G: START CAPTAIN LAB");
    else if (CounterWindowRemaining > 0.0f)
    { Cue = FString::Printf(TEXT("WARD BROKEN | OPEN %.1fs"), CounterWindowRemaining); Color = FColor(255,245,150); }
    else if (State == ENLEnemyState::Telegraph || State == ENLEnemyState::Attack)
    { Cue = State == ENLEnemyState::Telegraph ? TEXT("HEAVY WINDUP - WARD DOWN") : TEXT("HEAVY SLASH"); Color = FColor(255,135,75); }
    else if (State == ENLEnemyState::Recover || State == ENLEnemyState::Staggered)
    { Cue = TEXT("OPEN - COUNTER NOW"); Color = FColor(255,245,150); }
    else Cue = CaptainGuard->IsGuardActive() ? TEXT("FRONT WARD - BREAK OR FLANK") : TEXT("CAPTAIN APPROACH");
    StatusText->SetText(FText::FromString(FString::Printf(TEXT("HP %.0f | WARD %.0f | %s"),
        Vitals->GetHealth(), Vitals->GetGuard(), *Cue)));
    StatusText->SetTextRenderColor(Color);
}
