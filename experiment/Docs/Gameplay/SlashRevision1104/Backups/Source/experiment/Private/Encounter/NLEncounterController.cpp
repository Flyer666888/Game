#include "Encounter/NLEncounterController.h"

#include "AIController.h"
#include "AI/NLAttackDirectorSubsystem.h"
#include "AI/NLEnemyBrainComponent.h"
#include "AI/NLEnemyCharacter.h"
#include "Animation/AnimationAsset.h"
#include "Animation/AnimSequenceBase.h"
#include "Animation/SkeletalMeshActor.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Combat/NLCombatProjectile.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Encounter/NLWaveDefinition.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Player/NLVRGameMode.h"

DEFINE_LOG_CATEGORY_STATIC(LogNLEncounter, Log, All);

namespace
{
    constexpr int32 MaximumPlannedEnemies = 1024;
    constexpr int32 MaximumPlannedEnemiesPerWave = 512;
    constexpr int32 MaximumSpawnRetries = 32;
    constexpr int32 MaximumAliveEnemies = 12;

    bool IsValidDuration(float Value)
    {
        return FMath::IsFinite(Value) && Value >= 0.0f;
    }

    bool NameBefore(FName Left, FName Right)
    {
        return Left.ToString().Compare(Right.ToString(), ESearchCase::CaseSensitive) < 0;
    }
}

ANLEncounterController::ANLEncounterController()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bTickEvenWhenPaused = false;
    // BeginPlay prepares the plan and optional display poses; combat starts explicitly.
}

void ANLEncounterController::BeginPlay()
{
    Super::BeginPlay();
    ResetProgress(Seed);
    FName Reason;
    if (!BuildPlan(Reason))
    {
        FailEncounter(Reason);
    }
    else
    {
        UpdateReadyPreviews();
    }
}

void ANLEncounterController::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    bEndingPlay = true;
    ++EncounterGeneration;
    CleanupOwnedEnemies();
    Super::EndPlay(EndPlayReason);
}

bool ANLEncounterController::IsRunning() const
{
    return State == ENLEncounterState::Spawning || State == ENLEncounterState::WaitingClear
        || State == ENLEncounterState::Intermission;
}

bool ANLEncounterController::OwnsEnemy(const ANLEnemyCharacter* Enemy) const
{
    return Enemy && FindOwnedEnemy(Enemy) != nullptr;
}

int32 ANLEncounterController::GetWaveCount() const
{
    return RuntimeWaves.IsEmpty() ? Waves.Num() : RuntimeWaves.Num();
}

TArray<FName> ANLEncounterController::GetWaveIds() const
{
    TArray<FName> WaveIds;
    WaveIds.Reserve(RuntimeWaves.Num());
    for (const FRuntimeWave& Wave : RuntimeWaves) WaveIds.Add(Wave.WaveId);
    return WaveIds;
}

int32 ANLEncounterController::GetAliveCount() const
{
    int32 Count = 0;
    for (const FOwnedEnemy& Record : OwnedEnemies)
    {
        // Missing actors remain unresolved until the audit fails the encounter.
        if (Record.Generation == EncounterGeneration && Record.Terminal == EOwnedTerminal::Active)
        {
            ++Count;
        }
    }
    return Count;
}

int32 ANLEncounterController::GetReadyPreviewCount() const
{
    int32 Count = 0;
    for (const TWeakObjectPtr<ASkeletalMeshActor>& Preview : ReadyPreviews)
    {
        if (Preview.IsValid() && !Preview->IsActorBeingDestroyed()) ++Count;
    }
    return Count;
}

void ANLEncounterController::CleanupReadyPreviews()
{
    // These actors have no gameplay delegates, identities, vitals or AI. They
    // never enter OwnedEnemies or contribute to checkpoint/progression counts.
    for (const TWeakObjectPtr<ASkeletalMeshActor>& Preview : ReadyPreviews)
    {
        if (Preview.IsValid())
        {
            Preview->SetActorHiddenInGame(true);
            Preview->Destroy();
        }
    }
    ReadyPreviews.Reset();
    bReadyPreviewsBuilt = false;
    ReadyPreviewWaveIndex = INDEX_NONE;
}

void ANLEncounterController::UpdateReadyPreviews()
{
    UWorld* World = GetWorld();
    const ANLVRGameMode* VRMode = World ? World->GetAuthGameMode<ANLVRGameMode>() : nullptr;
    const bool bEnabled = bShowReadyPreviews || (VRMode && VRMode->bShowReadyEnemyPreviews);
    if (!bEnabled || (State != ENLEncounterState::Ready && State != ENLEncounterState::Cancelled))
    {
        if (bReadyPreviewsBuilt || !ReadyPreviews.IsEmpty()) CleanupReadyPreviews();
        return;
    }
    if (!World || bEndingPlay || bCleaningUp || bRestoringWaveEntry || bWaveEntryInProgress
        || !RuntimeWaves.IsValidIndex(ReadyStartingWaveIndex)) return;
    if (bReadyPreviewsBuilt && ReadyPreviewWaveIndex == ReadyStartingWaveIndex) return;
    CleanupReadyPreviews();
    // Record even an asset failure so it cannot cause per-frame spawn/load loops.
    bReadyPreviewsBuilt = true;
    ReadyPreviewWaveIndex = ReadyStartingWaveIndex;
    const FRuntimeWave& Wave = RuntimeWaves[ReadyStartingWaveIndex];
    const int32 PreviewLimit = FMath::Min(Wave.Plan.Num(), FMath::Clamp(Wave.MaxAlive, 1, MaximumAliveEnemies));
    TArray<FVector> UsedLocations;
    for (int32 Index = 0; Index < PreviewLimit; ++Index)
    {
        const FPlannedSpawn& Planned = Wave.Plan[Index];
        if (!Planned.EnemyClass || !Planned.CandidatePoints.IsValidIndex(Planned.InitialPointIndex)) continue;
        const ANLEnemyCharacter* Defaults = Planned.EnemyClass->GetDefaultObject<ANLEnemyCharacter>();
        const USkeletalMeshComponent* SourceMesh = Defaults ? Defaults->GetMesh() : nullptr;
        if (!SourceMesh) continue;
        const FNLWaveSpawnPoint& Point = Planned.CandidatePoints[Planned.InitialPointIndex];
        const FVector CapsuleLocation = Point.SpawnTransform.GetLocation();
        // Do not invent a different random choice when two plans share a point.
        // One entry pose is enough there; combat retains its collision retries.
        if (UsedLocations.ContainsByPredicate([&CapsuleLocation](const FVector& Existing)
            { return FVector::DistSquared(Existing, CapsuleLocation) < FMath::Square(56.0f); })) continue;
        USkeletalMesh* MeshAsset = Defaults->EnemySkeletalMesh
            ? Defaults->EnemySkeletalMesh.Get() : SourceMesh->GetSkeletalMeshAsset();
        if (!MeshAsset) MeshAsset = LoadObject<USkeletalMesh>(nullptr,
            TEXT("/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Combat.SK_WuxiaMale_Combat"));
        if (!MeshAsset) MeshAsset = LoadObject<USkeletalMesh>(nullptr,
            TEXT("/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Feet.SK_WuxiaMale_Feet"));
        UAnimationAsset* Idle = Defaults->IdleAnimation;
        if (!Idle) Idle = LoadObject<UAnimationAsset>(nullptr,
            TEXT("/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Idle_Planted.Wuxia_Idle_Planted"));
        if (!MeshAsset || !Idle)
        {
            UE_LOG(LogNLEncounter, Warning, TEXT("%s: Ready preview ordinal %d missing mesh/idle; skipped."),
                *GetName(), Planned.SpawnOrdinal);
            continue;
        }

        FTransform MeshRelative = SourceMesh->GetRelativeTransform();
        FHitResult FloorHit;
        FCollisionQueryParams FloorQuery(SCENE_QUERY_STAT(NLReadyPreviewFloor), false, this);
        if (World->LineTraceSingleByChannel(FloorHit, CapsuleLocation + FVector(0.0, 0.0, 20.0),
            CapsuleLocation - FVector(0.0, 0.0, 250.0), ECC_Pawn, FloorQuery)
            && FloorHit.bBlockingHit && FloorHit.ImpactNormal.Z >= 0.7f)
        {
            // Match NLEnemyCharacter::Tick's standing-floor mesh compensation.
            // Preserve the authored mesh rotation/scale and all horizontal offsets.
            FVector MeshOffset = MeshRelative.GetLocation();
            MeshOffset.Z = FloorHit.ImpactPoint.Z - CapsuleLocation.Z;
            MeshRelative.SetLocation(MeshOffset);
        }
        const FTransform MeshWorld = MeshRelative * Point.SpawnTransform;
        FActorSpawnParameters Params;
        Params.Owner = this;
        Params.ObjectFlags |= RF_Transient;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        ASkeletalMeshActor* Preview = World->SpawnActor<ASkeletalMeshActor>(ASkeletalMeshActor::StaticClass(), MeshWorld, Params);
        if (!Preview) continue;
        ReadyPreviews.Add(Preview);
        UsedLocations.Add(CapsuleLocation);
        Preview->Tags.Add(TEXT("NL_ReadyEnemyPreview"));
        Preview->Tags.Add(FName(*FString::Printf(TEXT("NL_ReadyWave_%s"), *Wave.WaveId.ToString())));
        Preview->Tags.Add(FName(*FString::Printf(TEXT("NL_ReadyEntry_%s"), *Planned.EntryId.ToString())));
        Preview->Tags.Add(FName(*FString::Printf(TEXT("NL_ReadyOrdinal_%d"), Planned.SpawnOrdinal)));
        Preview->Tags.Add(FName(*FString::Printf(TEXT("NL_ReadyPoint_%s"), *Point.SpawnPointId.ToString())));
        Preview->SetActorEnableCollision(false);
        Preview->SetCanBeDamaged(false);
        Preview->SetReplicates(false);
        Preview->SetActorTickEnabled(false);
        Preview->bShouldDoAnimNotifies = false;
        USkeletalMeshComponent* Mesh = Preview->GetSkeletalMeshComponent();
        Mesh->SetMobility(EComponentMobility::Movable);
        Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Mesh->SetGenerateOverlapEvents(false);
        Mesh->SetCanEverAffectNavigation(false);
        Mesh->SetSimulatePhysics(false);
        Mesh->SetSkeletalMeshAsset(MeshAsset);
        for (int32 Material = 0; Material < SourceMesh->GetNumMaterials(); ++Material)
        {
            if (UMaterialInterface* SourceMaterial = SourceMesh->GetMaterial(Material)) Mesh->SetMaterial(Material, SourceMaterial);
        }
        Mesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
        Mesh->PrimaryComponentTick.bTickEvenWhenPaused = false;
        Mesh->PlayAnimation(Idle, true);
        if (!Defaults->GripMorphName.IsNone() && MeshAsset->FindMorphTarget(Defaults->GripMorphName))
            Mesh->SetMorphTarget(Defaults->GripMorphName, FMath::Clamp(Defaults->GripMorphWeight, 0.0f, 1.0f));
        Mesh->TickAnimation(0.0f, false);
        Mesh->RefreshBoneTransforms();

        if (Defaults->bShowSword)
        {
            // Enemy BeginPlay uses this mesh, even when the CDO Sword is empty.
            UStaticMesh* SwordAsset = LoadObject<UStaticMesh>(nullptr,
                TEXT("/Game/ReversedScale/Weapons/Yueyao/SM_Yueyao_Player.SM_Yueyao_Player"));
            if (SwordAsset)
            {
                UStaticMeshComponent* PreviewSword = NewObject<UStaticMeshComponent>(Preview, TEXT("ReadySword"));
                Preview->AddInstanceComponent(PreviewSword);
                PreviewSword->SetupAttachment(Mesh, TEXT("hand_r"));
                PreviewSword->SetRelativeTransform(Defaults->SwordGripTransform);
                PreviewSword->SetMobility(EComponentMobility::Movable);
                PreviewSword->SetStaticMesh(SwordAsset);
                PreviewSword->SetCollisionEnabled(ECollisionEnabled::NoCollision);
                PreviewSword->SetGenerateOverlapEvents(false);
                PreviewSword->SetCanEverAffectNavigation(false);
                if (Defaults->Sword)
                {
                    for (int32 Material = 0; Material < Defaults->Sword->GetNumMaterials(); ++Material)
                        if (UMaterialInterface* SourceMaterial = Defaults->Sword->GetMaterial(Material))
                            PreviewSword->SetMaterial(Material, SourceMaterial);
                }
                PreviewSword->RegisterComponent();
            }
        }
        UTextRenderComponent* Label = NewObject<UTextRenderComponent>(Preview, TEXT("ReadyLabel"));
        Preview->AddInstanceComponent(Label);
        Label->SetupAttachment(Mesh);
        Label->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Label->SetCanEverAffectNavigation(false);
        Label->SetHorizontalAlignment(EHTA_Center);
        Label->SetVerticalAlignment(EVRTA_TextCenter);
        Label->SetWorldSize(6.0f);
        Label->SetTextRenderColor(FColor(210, 215, 190));
        Label->SetText(FText::FromString(TEXT("READY / WAITING FOR START")));
        Label->RegisterComponent();
        Label->SetWorldLocationAndRotation(CapsuleLocation + FVector(0.0, 0.0, 107.0), Point.SpawnTransform.GetRotation());
        Mesh->bPauseAnims = bEncounterPaused;
        UE_LOG(LogNLEncounter, Log, TEXT("%s: Ready preview ordinal=%d point=%s capsule=%s mesh=%s grip=%.2f"),
            *GetName(), Planned.SpawnOrdinal, *Point.SpawnPointId.ToString(), *CapsuleLocation.ToCompactString(),
            *MeshWorld.GetLocation().ToCompactString(), Defaults->GripMorphWeight);
    }
    UE_LOG(LogNLEncounter, Log, TEXT("%s: Ready wave=%d display=%d combatSpawned=%d alive=%d; displays have no gameplay components."),
        *GetName(), ReadyStartingWaveIndex, GetReadyPreviewCount(), SpawnedCount, GetAliveCount());
}

int32 ANLEncounterController::GetCurrentWavePlannedCount() const
{
    return RuntimeWaves.IsValidIndex(CurrentWaveIndex) ? RuntimeWaves[CurrentWaveIndex].Plan.Num() : 0;
}

int32 ANLEncounterController::GetCurrentWaveSpawnedCount() const
{
    return RuntimeWaves.IsValidIndex(CurrentWaveIndex) ? RuntimeWaves[CurrentWaveIndex].SpawnedCount : 0;
}

float ANLEncounterController::GetIntermissionRemaining() const
{
    return State == ENLEncounterState::Intermission
        ? static_cast<float>(FMath::Max(0.0, IntermissionEndsAt - GetEncounterTime())) : 0.0f;
}

double ANLEncounterController::GetEncounterTime() const
{
    if (!GetWorld()) return 0.0;
    const double WorldTime = bEncounterPaused ? PauseBeganWorldTime : GetWorld()->GetTimeSeconds();
    return WorldTime - AccumulatedPauseSeconds;
}

void ANLEncounterController::ResetProgress(int32 InSeed)
{
    CleanupReadyPreviews();
    Seed = InitialSeed = InSeed;
    CompositionRandom.Initialize(InSeed);
    RuntimeWaves.Reset();
    RuntimeEnemyClasses.Reset();
    OwnedEnemies.Reset();
    CurrentWaveIndex = INDEX_NONE;
    ReadyStartingWaveIndex = 0;
    PlannedCount = SpawnedCount = DefeatedCount = FailedSpawnCount = CompletedWaveCount = 0;
    NextSpawnAt = IntermissionEndsAt = 0.0;
    PauseBeganWorldTime = AccumulatedPauseSeconds = 0.0;
    FailureReason = NAME_None;
    CheckpointRestoreFailureReason = NAME_None;
    bEncounterPaused = false;
    bTerminalOutcomeEmitted = false;
    bSpawnInProgress = false;
    bObjectiveSpawningStopped = false;
}

bool ANLEncounterController::BuildPlan(FName& OutFailure)
{
    if (!BuildPlanForSeed(InitialSeed, RuntimeWaves, RuntimeEnemyClasses, CompositionRandom, PlannedCount, OutFailure))
        return false;
    RuntimeMaxSpawnsPerTick = MaxSpawnsPerTick;
    RuntimeCorpseHoldSeconds = CorpseHoldSeconds;
    return true;
}

bool ANLEncounterController::BuildPlanForSeed(int32 InSeed, TArray<FRuntimeWave>& OutWaves,
    TArray<TSubclassOf<ANLEnemyCharacter>>& OutEnemyClasses, FRandomStream& OutRandom,
    int32& OutPlannedCount, FName& OutFailure) const
{
    OutWaves.Reset();
    OutEnemyClasses.Reset();
    OutPlannedCount = 0;
    OutRandom.Initialize(InSeed);
    OutFailure = TEXT("InvalidWaveConfig");
    auto Reject = [this, &OutWaves, &OutEnemyClasses, &OutPlannedCount, &OutFailure](FName Reason, const FString& Detail)
    {
        OutFailure = Reason;
        UE_LOG(LogNLEncounter, Error, TEXT("%s: invalid wave configuration (%s): %s"), *GetName(), *Reason.ToString(), *Detail);
        OutWaves.Reset();
        OutEnemyClasses.Reset();
        OutPlannedCount = 0;
        return false;
    };

    if (Waves.IsEmpty() || Waves.Num() > MaximumPlannedEnemies)
        return Reject(TEXT("InvalidWaveCount"), TEXT("Waves must contain between 1 and 1024 definitions."));
    if (!IsValidDuration(CorpseHoldSeconds))
        return Reject(TEXT("InvalidCorpseHold"), TEXT("CorpseHoldSeconds must be finite and nonnegative."));
    if (MaxSpawnsPerTick < 1 || MaxSpawnsPerTick > MaximumAliveEnemies)
        return Reject(TEXT("InvalidSpawnBudget"), TEXT("MaxSpawnsPerTick must be between 1 and 12."));

    TMap<FName, FNLWaveSpawnPoint> PointsById;
    for (const FNLWaveSpawnPoint& Point : SpawnPoints)
    {
        const FVector Scale = Point.SpawnTransform.GetScale3D();
        if (Point.SpawnPointId.IsNone())
            return Reject(TEXT("InvalidSpawnPointId"), TEXT("Spawn points require nonempty SpawnPointId values."));
        if (PointsById.Contains(Point.SpawnPointId))
            return Reject(TEXT("DuplicateSpawnPointId"), FString::Printf(TEXT("Spawn point %s is repeated."), *Point.SpawnPointId.ToString()));
        if (Point.SpawnTransform.ContainsNaN() || !Point.SpawnTransform.GetRotation().IsNormalized()
            || Scale.X <= 0.0 || Scale.Y <= 0.0 || Scale.Z <= 0.0)
            return Reject(TEXT("InvalidSpawnPointTransform"), FString::Printf(TEXT("Spawn point %s has an invalid world capsule transform."), *Point.SpawnPointId.ToString()));
        PointsById.Add(Point.SpawnPointId, Point);
    }

    TArray<FRuntimeWave> NewWaves;
    TSet<FName> WaveIds;
    int32 TotalCount = 0;
    for (UNLWaveDefinition* Definition : Waves)
    {
        if (!IsValid(Definition)) return Reject(TEXT("MissingWaveDefinition"), TEXT("A wave definition is missing."));
        if (Definition->WaveId.IsNone())
            return Reject(TEXT("InvalidWaveId"), TEXT("Wave definitions require nonempty WaveId values."));
        if (WaveIds.Contains(Definition->WaveId))
            return Reject(TEXT("DuplicateWaveId"), FString::Printf(TEXT("Wave %s is repeated."), *Definition->WaveId.ToString()));
        WaveIds.Add(Definition->WaveId);
        if (Definition->SpawnEntries.IsEmpty())
            return Reject(TEXT("MissingSpawnEntries"), FString::Printf(TEXT("Wave %s has no spawn entries."), *Definition->WaveId.ToString()));
        if (!IsValidDuration(Definition->SpawnIntervalSeconds) || !IsValidDuration(Definition->IntermissionSeconds)
            || !IsValidDuration(Definition->RetryDelaySeconds))
            return Reject(TEXT("InvalidWaveTiming"), TEXT("Wave timing values must be finite and nonnegative."));
        if (Definition->MaxAlive < 1 || Definition->MaxAlive > MaximumAliveEnemies)
            return Reject(TEXT("InvalidAliveLimit"), TEXT("MaxAlive must be between 1 and 12; it is independent of attack slots."));
        if (Definition->MaxSpawnRetries < 0 || Definition->MaxSpawnRetries > MaximumSpawnRetries)
            return Reject(TEXT("InvalidSpawnRetryLimit"), TEXT("MaxSpawnRetries must be between 0 and 32."));

        FRuntimeWave Wave;
        Wave.WaveId = Definition->WaveId;
        Wave.SpawnIntervalSeconds = Definition->SpawnIntervalSeconds;
        Wave.IntermissionSeconds = Definition->IntermissionSeconds;
        Wave.RetryDelaySeconds = Definition->RetryDelaySeconds;
        Wave.MaxAlive = Definition->MaxAlive;
        Wave.MaxSpawnRetries = Definition->MaxSpawnRetries;
        TArray<FNLWaveSpawnEntry> Entries = Definition->SpawnEntries;
        Entries.Sort([](const FNLWaveSpawnEntry& Left, const FNLWaveSpawnEntry& Right)
        {
            return NameBefore(Left.EntryId, Right.EntryId);
        });
        TSet<FName> EntryIds;
        for (const FNLWaveSpawnEntry& Entry : Entries)
        {
            UClass* EnemyClass = Entry.EnemyClass.Get();
            if (Entry.EntryId.IsNone())
                return Reject(TEXT("InvalidEntryId"), TEXT("Each wave requires nonempty EntryId values."));
            if (EntryIds.Contains(Entry.EntryId))
                return Reject(TEXT("DuplicateEntryId"), FString::Printf(TEXT("Entry %s is repeated in wave %s."), *Entry.EntryId.ToString(), *Definition->WaveId.ToString()));
            EntryIds.Add(Entry.EntryId);
            if (!EnemyClass || !EnemyClass->IsChildOf(ANLEnemyCharacter::StaticClass())
                || EnemyClass->HasAnyClassFlags(CLASS_Abstract | CLASS_Deprecated | CLASS_NewerVersionExists))
                return Reject(TEXT("InvalidEnemyClass"), FString::Printf(TEXT("Entry %s has no spawnable enemy class."), *Entry.EntryId.ToString()));
            if (Entry.Count < 1 || Entry.Count > MaximumPlannedEnemies - TotalCount
                || Entry.Count > MaximumPlannedEnemiesPerWave - Wave.Plan.Num())
                return Reject(TEXT("InvalidEntryCount"), TEXT("Entry counts must be positive; an encounter is capped at 1024 planned enemies and each wave at 512."));
            if (Entry.SpawnPointIds.IsEmpty())
                return Reject(TEXT("MissingEntrySpawnPoints"), FString::Printf(TEXT("Entry %s has no candidate spawn points."), *Entry.EntryId.ToString()));

            TArray<FName> CandidateIds = Entry.SpawnPointIds;
            CandidateIds.Sort([](FName Left, FName Right) { return NameBefore(Left, Right); });
            TArray<FNLWaveSpawnPoint> Candidates;
            TSet<FName> SeenPointIds;
            for (FName PointId : CandidateIds)
            {
                const FNLWaveSpawnPoint* Point = PointsById.Find(PointId);
                if (!Point)
                    return Reject(TEXT("UnknownSpawnPointId"), FString::Printf(TEXT("Entry %s references missing spawn point %s."), *Entry.EntryId.ToString(), *PointId.ToString()));
                if (SeenPointIds.Contains(PointId))
                    return Reject(TEXT("DuplicateEntrySpawnPointId"), FString::Printf(TEXT("Entry %s repeats spawn point %s."), *Entry.EntryId.ToString(), *PointId.ToString()));
                SeenPointIds.Add(PointId);
                Candidates.Add(*Point);
            }
            OutEnemyClasses.AddUnique(Entry.EnemyClass);
            for (int32 InstanceIndex = 0; InstanceIndex < Entry.Count; ++InstanceIndex)
            {
                FPlannedSpawn Planned;
                Planned.EnemyClass = Entry.EnemyClass;
                Planned.EntryId = Entry.EntryId;
                Planned.CandidatePoints = Candidates;
                Planned.InitialPointIndex = OutRandom.RandRange(0, Candidates.Num() - 1);
                Wave.Plan.Add(MoveTemp(Planned));
            }
            TotalCount += Entry.Count;
        }
        // This stream is used only for composition. Retries cycle authored points
        // without consuming randomness, so collision outcomes cannot reorder later waves.
        for (int32 Index = Wave.Plan.Num() - 1; Index > 0; --Index)
        {
            Wave.Plan.Swap(Index, OutRandom.RandRange(0, Index));
        }
        NewWaves.Add(MoveTemp(Wave));
    }

    int32 Ordinal = 0;
    for (FRuntimeWave& Wave : NewWaves)
    {
        for (FPlannedSpawn& Planned : Wave.Plan) Planned.SpawnOrdinal = Ordinal++;
    }
    OutWaves = MoveTemp(NewWaves);
    OutPlannedCount = TotalCount;
    OutFailure = NAME_None;
    return true;
}

bool ANLEncounterController::BuildValidatedWaveEntry(int32 InInitialSeed, int32 EntryWaveIndex,
    int32 ExpectedRandomState, const TArray<FName>& ExpectedWaveIds, TArray<FRuntimeWave>& OutWaves,
    TArray<TSubclassOf<ANLEnemyCharacter>>& OutEnemyClasses, FRandomStream& OutRandom,
    int32& OutPlannedCount, FName& OutReason) const
{
    OutReason = NAME_None;
    auto Reject = [this, &OutReason](FName Reason, const FString& Detail)
    {
        OutReason = Reason;
        UE_LOG(LogNLEncounter, Warning, TEXT("%s: checkpoint rejected (%s): %s"), *GetName(), *Reason.ToString(), *Detail);
        return false;
    };
    if (bEndingPlay || bCleaningUp || bRestoringWaveEntry)
        return Reject(TEXT("CheckpointRestoreBusy"), TEXT("The encounter is restoring or shutting down."));
    if (!bEnableCheckpoints)
        return Reject(TEXT("CheckpointsDisabled"), TEXT("This encounter does not enable section-entry checkpoints."));
    if (LevelId.IsNone())
        return Reject(TEXT("InvalidCheckpointLevelId"), TEXT("LevelId is empty."));
    if (EncounterId.IsNone())
        return Reject(TEXT("InvalidCheckpointEncounterId"), TEXT("EncounterId is empty."));
    if (ContentRevision.IsNone())
        return Reject(TEXT("InvalidCheckpointContentRevision"), TEXT("ContentRevision is empty."));
    TSet<FName> SavedIds;
    for (FName WaveId : ExpectedWaveIds)
    {
        if (WaveId.IsNone())
            return Reject(TEXT("InvalidCheckpointWaveId"), TEXT("The snapshot contains an empty wave ID."));
        if (SavedIds.Contains(WaveId))
            return Reject(TEXT("DuplicateCheckpointWaveId"), FString::Printf(TEXT("The snapshot repeats wave ID %s."), *WaveId.ToString()));
        SavedIds.Add(WaveId);
    }
    // Planning is isolated from live state. Every int32 seed is valid for
    // FRandomStream; the rebuilt final state verifies the saved seed/state pair.
    if (!BuildPlanForSeed(InInitialSeed, OutWaves, OutEnemyClasses, OutRandom, OutPlannedCount, OutReason)) return false;
    if (ExpectedWaveIds.Num() != OutWaves.Num())
        return Reject(TEXT("CheckpointWaveIdsMismatch"), TEXT("The snapshot wave count differs from the authored encounter."));
    for (int32 Index = 0; Index < OutWaves.Num(); ++Index)
    {
        if (ExpectedWaveIds[Index] != OutWaves[Index].WaveId)
            return Reject(TEXT("CheckpointWaveIdsMismatch"), FString::Printf(TEXT("Wave %d saved ID %s differs from authored ID %s."),
                Index, *ExpectedWaveIds[Index].ToString(), *OutWaves[Index].WaveId.ToString()));
    }
    if (!OutWaves.IsValidIndex(EntryWaveIndex))
        return Reject(TEXT("InvalidCheckpointWaveIndex"), FString::Printf(TEXT("Entry wave index %d is outside this encounter."), EntryWaveIndex));
    if (ExpectedRandomState != OutRandom.GetCurrentSeed())
        return Reject(TEXT("CheckpointRandomStateMismatch"), FString::Printf(TEXT("Seed %d rebuilds state %d instead of saved state %d."),
            InInitialSeed, OutRandom.GetCurrentSeed(), ExpectedRandomState));
    return true;
}

bool ANLEncounterController::CanRestoreWaveEntry(int32 InInitialSeed, int32 EntryWaveIndex,
    int32 ExpectedRandomState, const TArray<FName>& ExpectedWaveIds, FName& OutReason) const
{
    TArray<FRuntimeWave> CandidateWaves;
    TArray<TSubclassOf<ANLEnemyCharacter>> CandidateClasses;
    FRandomStream CandidateRandom;
    int32 CandidatePlannedCount = 0;
    return BuildValidatedWaveEntry(InInitialSeed, EntryWaveIndex, ExpectedRandomState, ExpectedWaveIds,
        CandidateWaves, CandidateClasses, CandidateRandom, CandidatePlannedCount, OutReason);
}

void ANLEncounterController::ApplyReadyWaveEntry(int32 EntryWaveIndex)
{
    ReadyStartingWaveIndex = EntryWaveIndex;
    CurrentWaveIndex = INDEX_NONE;
    CompletedWaveCount = EntryWaveIndex;
    SpawnedCount = DefeatedCount = 0;
    for (int32 Index = 0; Index < EntryWaveIndex; ++Index)
    {
        FRuntimeWave& Wave = RuntimeWaves[Index];
        Wave.NextPlanIndex = Wave.SpawnedCount = Wave.Plan.Num();
        SpawnedCount += Wave.Plan.Num();
        DefeatedCount += Wave.Plan.Num();
    }
    // Prior waves contribute progress only. No enemy/death delegate is replayed.
}

bool ANLEncounterController::RestoreWaveEntry(int32 InInitialSeed, int32 EntryWaveIndex,
    int32 ExpectedRandomState, const TArray<FName>& ExpectedWaveIds)
{
    TArray<FRuntimeWave> CandidateWaves;
    TArray<TSubclassOf<ANLEnemyCharacter>> CandidateClasses;
    FRandomStream CandidateRandom;
    int32 CandidatePlannedCount = 0;
    FName Reason;
    if (!BuildValidatedWaveEntry(InInitialSeed, EntryWaveIndex, ExpectedRandomState, ExpectedWaveIds,
        CandidateWaves, CandidateClasses, CandidateRandom, CandidatePlannedCount, Reason))
    {
        CheckpointRestoreFailureReason = Reason;
        return false;
    }
    // Synchronous state delegates cannot start/cancel another encounter midway
    // through cleanup. The player holds its own input/update lock around this.
    TGuardValue<bool> RestoreGuard(bRestoringWaveEntry, true);
    ++EncounterGeneration;
    const uint64 Generation = EncounterGeneration;
    CleanupOwnedEnemies();
    ResetProgress(InInitialSeed);
    RuntimeWaves = MoveTemp(CandidateWaves);
    RuntimeEnemyClasses = MoveTemp(CandidateClasses);
    CompositionRandom = CandidateRandom;
    PlannedCount = CandidatePlannedCount;
    RuntimeMaxSpawnsPerTick = MaxSpawnsPerTick;
    RuntimeCorpseHoldSeconds = CorpseHoldSeconds;
    ApplyReadyWaveEntry(EntryWaveIndex);
    SetState(ENLEncounterState::Ready);
    if (bEndingPlay || EncounterGeneration != Generation)
    {
        CheckpointRestoreFailureReason = TEXT("CheckpointRestoreInterrupted");
        return false;
    }
    CheckpointRestoreFailureReason = NAME_None;
    return true;
}

void ANLEncounterController::StartEncounter()
{
    if (bEndingPlay || bCleaningUp || bRestoringWaveEntry || bWaveEntryInProgress
        || (State != ENLEncounterState::Ready && State != ENLEncounterState::Cancelled)) return;
    const bool bWasPaused = bEncounterPaused;
    const int32 EntryWaveIndex = ReadyStartingWaveIndex;
    ++EncounterGeneration;
    CleanupOwnedEnemies();
    ResetProgress(Seed);
    ReadyStartingWaveIndex = EntryWaveIndex;
    const uint64 Generation = EncounterGeneration;
    SetState(ENLEncounterState::Ready);
    if (EncounterGeneration != Generation || State != ENLEncounterState::Ready) return;
    FName Reason;
    if (!BuildPlan(Reason))
    {
        FailEncounter(Reason);
        return;
    }
    if (!RuntimeWaves.IsValidIndex(EntryWaveIndex))
    {
        FailEncounter(TEXT("InvalidCheckpointWaveIndex"));
        return;
    }
    ApplyReadyWaveEntry(EntryWaveIndex);
    if (bWasPaused) SetEncounterPaused(true);
    BeginWave(EntryWaveIndex);
    // Start only changes state. The first spawn happens in a subsequent Tick.
}

void ANLEncounterController::StopSpawningForObjective()
{
    if (bEndingPlay || bCleaningUp || bRestoringWaveEntry || !IsRunning()) return;
    bObjectiveSpawningStopped = true;
    NextSpawnAt = IntermissionEndsAt = 0.0;
    SetState(ENLEncounterState::WaitingClear);
}

void ANLEncounterController::CancelEncounter()
{
    if (bEndingPlay || bCleaningUp || bRestoringWaveEntry) return;
    const bool bCanBecomeCancelled = State == ENLEncounterState::Ready || State == ENLEncounterState::Cancelled || IsRunning();
    ++EncounterGeneration;
    CleanupOwnedEnemies();
    bSpawnInProgress = false;
    NextSpawnAt = IntermissionEndsAt = 0.0;
    if (bCanBecomeCancelled) SetState(ENLEncounterState::Cancelled);
}

void ANLEncounterController::ResetEncounterForRetry(int32 InSeed, bool bStartImmediately)
{
    if (bEndingPlay || bCleaningUp || bRestoringWaveEntry) return;
    ++EncounterGeneration;
    CleanupOwnedEnemies();
    ResetProgress(InSeed);
    const uint64 Generation = EncounterGeneration;
    SetState(ENLEncounterState::Ready);
    if (EncounterGeneration != Generation || State != ENLEncounterState::Ready) return;
    FName Reason;
    if (!BuildPlan(Reason))
    {
        FailEncounter(Reason);
        return;
    }
    if (bStartImmediately) StartEncounter();
}

void ANLEncounterController::SetEncounterPaused(bool bPaused)
{
    if (bEndingPlay || bCleaningUp || bRestoringWaveEntry || bEncounterPaused == bPaused || !GetWorld()) return;
    const double Now = GetWorld()->GetTimeSeconds();
    if (bPaused)
    {
        PauseBeganWorldTime = Now;
    }
    else
    {
        AccumulatedPauseSeconds += FMath::Max(0.0, Now - PauseBeganWorldTime);
        PauseBeganWorldTime = 0.0;
    }
    bEncounterPaused = bPaused;
    for (const TWeakObjectPtr<ASkeletalMeshActor>& Preview : ReadyPreviews)
        if (Preview.IsValid()) Preview->GetSkeletalMeshComponent()->bPauseAnims = bPaused;
    ANLCombatProjectile::SetEncounterProjectilesPaused(this, bPaused);
    const uint64 Generation = EncounterGeneration;
    // Copy weak handles because an external delegate may cancel/reset during a pause.
    TArray<TWeakObjectPtr<ANLEnemyCharacter>> Enemies;
    for (const FOwnedEnemy& Record : OwnedEnemies) Enemies.Add(Record.Enemy);
    for (const TWeakObjectPtr<ANLEnemyCharacter>& WeakEnemy : Enemies)
    {
        if (EncounterGeneration != Generation) return;
        if (ANLEnemyCharacter* Enemy = WeakEnemy.Get())
        {
            Enemy->SetLabPaused(bPaused || State == ENLEncounterState::Failed);
            // A controller-only pause must freeze animation/movement as well as its clock.
            Enemy->SetActorTickEnabled(!bPaused);
            Enemy->GetMesh()->SetComponentTickEnabled(!bPaused);
            Enemy->GetCharacterMovement()->SetComponentTickEnabled(!bPaused && State != ENLEncounterState::Failed);
            if (AAIController* AI = Cast<AAIController>(Enemy->GetController()))
                AI->SetActorTickEnabled(!bPaused && State != ENLEncounterState::Failed);
        }
    }
    if (EncounterGeneration == Generation) OnPauseChanged.Broadcast(bPaused);
}

void ANLEncounterController::FailEncounter(FName Reason)
{
    if (bEndingPlay || bCleaningUp || bRestoringWaveEntry || State == ENLEncounterState::Failed || State == ENLEncounterState::Completed
        || State == ENLEncounterState::Cancelled) return;
    FailureReason = Reason.IsNone() ? FName(TEXT("InvalidWaveConfig")) : Reason;
    ANLCombatProjectile::DestroyEncounterProjectiles(this);
    NextSpawnAt = IntermissionEndsAt = 0.0;
    const uint64 Generation = EncounterGeneration;
    SetState(ENLEncounterState::Failed);
    if (EncounterGeneration != Generation || State != ENLEncounterState::Failed) return;
    StopOwnedEnemies();
    if (EncounterGeneration != Generation || State != ENLEncounterState::Failed || bTerminalOutcomeEmitted) return;
    bTerminalOutcomeEmitted = true;
    UE_LOG(LogNLEncounter, Warning, TEXT("%s failed: %s (wave=%d spawned=%d defeated=%d)"),
        *GetName(), *FailureReason.ToString(), CurrentWaveIndex, SpawnedCount, DefeatedCount);
    OnEncounterFailed.Broadcast(FailureReason);
}

void ANLEncounterController::BeginWave(int32 WaveIndex)
{
    if (bEndingPlay || bCleaningUp || bRestoringWaveEntry || bWaveEntryInProgress) return;
    if (!RuntimeWaves.IsValidIndex(WaveIndex))
    {
        FailEncounter(TEXT("InvalidWaveConfig"));
        return;
    }
    const uint64 Generation = EncounterGeneration;
    CurrentWaveIndex = WaveIndex;
    NextSpawnAt = GetEncounterTime();
    TGuardValue<bool> EntryGuard(bWaveEntryInProgress, true);
    if (bEnableCheckpoints)
    {
        ReadyStartingWaveIndex = WaveIndex;
        OnWaveEntryReady.Broadcast(WaveIndex);
        // Entry listeners may synchronously fail, cancel, reset or restore.
        // A superseded plan must never enter Spawning after that callback.
        if (EncounterGeneration != Generation || CurrentWaveIndex != WaveIndex || bEndingPlay || bCleaningUp
            || bRestoringWaveEntry || State == ENLEncounterState::Failed || State == ENLEncounterState::Cancelled) return;
    }
    SetState(ENLEncounterState::Spawning);
}

void ANLEncounterController::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    UpdateReadyPreviews();
    if (bEndingPlay || bCleaningUp || bRestoringWaveEntry || bWaveEntryInProgress || bEncounterPaused
        || !GetWorld() || GetWorld()->IsPaused()) return;
    const uint64 Generation = EncounterGeneration;
    CleanupExpiredCorpses();
    if (EncounterGeneration != Generation || !IsRunning()) return;
    AuditOwnedEnemies();
    if (EncounterGeneration != Generation || !IsRunning()) return;
    if (bObjectiveSpawningStopped) return;

    if (State == ENLEncounterState::Intermission)
    {
        if (GetEncounterTime() >= IntermissionEndsAt) BeginWave(CurrentWaveIndex + 1);
        return;
    }
    if (State == ENLEncounterState::Spawning)
    {
        // Each attempt, including a failure with a zero retry delay, consumes budget.
        for (int32 Attempt = 0; Attempt < RuntimeMaxSpawnsPerTick; ++Attempt)
        {
            if (EncounterGeneration != Generation || State != ENLEncounterState::Spawning || bEncounterPaused) return;
            if (!RuntimeWaves.IsValidIndex(CurrentWaveIndex))
            {
                FailEncounter(TEXT("InvalidWaveConfig"));
                return;
            }
            const FRuntimeWave& Wave = RuntimeWaves[CurrentWaveIndex];
            if (Wave.NextPlanIndex >= Wave.Plan.Num() || GetAliveCount() >= Wave.MaxAlive
                || GetEncounterTime() < NextSpawnAt || bSpawnInProgress) break;
            if (!TrySpawnNext()) break;
        }
    }
    if (EncounterGeneration == Generation && IsRunning() && !bEncounterPaused) EvaluateWaveClear();
}

bool ANLEncounterController::TrySpawnNext()
{
    if (bObjectiveSpawningStopped) return false;
    if (!RuntimeWaves.IsValidIndex(CurrentWaveIndex)) return false;
    FRuntimeWave& Wave = RuntimeWaves[CurrentWaveIndex];
    if (!Wave.Plan.IsValidIndex(Wave.NextPlanIndex)) return false;
    // Do not keep plan references across construction scripts or state delegates.
    const FPlannedSpawn Planned = Wave.Plan[Wave.NextPlanIndex];
    const int32 WaveIndex = CurrentWaveIndex;
    const int32 PlanIndex = Wave.NextPlanIndex;
    const uint64 Generation = EncounterGeneration;
    const int32 PointIndex = (Planned.InitialPointIndex + Planned.FailedAttempts) % Planned.CandidatePoints.Num();
    const FNLWaveSpawnPoint& Point = Planned.CandidatePoints[PointIndex];
    bSpawnInProgress = true;
    ANLEnemyCharacter* Enemy = GetWorld()->SpawnActorDeferred<ANLEnemyCharacter>(Planned.EnemyClass,
        Point.SpawnTransform, this, GetInstigator(), ESpawnActorCollisionHandlingMethod::DontSpawnIfColliding);
    if (IsValid(Enemy)) Enemy->FinishSpawning(Point.SpawnTransform);
    if (EncounterGeneration != Generation || State != ENLEncounterState::Spawning || bEndingPlay)
    {
        if (EncounterGeneration == Generation) bSpawnInProgress = false;
        if (IsValid(Enemy))
        {
            AAIController* AI = Cast<AAIController>(Enemy->GetController());
            Enemy->SetCombatEnabled(false);
            Enemy->GetEnemyBrain()->Despawn();
            Enemy->Destroy();
            if (IsValid(AI)) AI->Destroy();
        }
        return false;
    }
    bSpawnInProgress = false;
    if (!IsValid(Enemy))
    {
        FPlannedSpawn& Pending = RuntimeWaves[WaveIndex].Plan[PlanIndex];
        ++Pending.FailedAttempts;
        ++FailedSpawnCount;
        NextSpawnAt = GetEncounterTime() + RuntimeWaves[WaveIndex].RetryDelaySeconds;
        UE_LOG(LogNLEncounter, Warning, TEXT("%s: spawn ordinal %d at %s failed (attempt %d/%d)"),
            *GetName(), Planned.SpawnOrdinal, *Point.SpawnPointId.ToString(), Pending.FailedAttempts,
            RuntimeWaves[WaveIndex].MaxSpawnRetries + 1);
        if (Pending.FailedAttempts > RuntimeWaves[WaveIndex].MaxSpawnRetries) FailEncounter(TEXT("SpawnFailed"));
        return false;
    }

    UNLEnemyBrainComponent* Brain = Enemy->GetEnemyBrain();
    UNLCombatIdentityComponent* Identity = Enemy->CombatIdentity;
    if (!Brain || !Identity || !Enemy->Vitals)
    {
        AAIController* AI = Cast<AAIController>(Enemy->GetController());
        Enemy->Destroy();
        if (IsValid(AI)) AI->Destroy();
        ++FailedSpawnCount;
        FailEncounter(TEXT("SpawnFailed"));
        return false;
    }

    FOwnedEnemy Record;
    Record.Enemy = Enemy;
    Record.SpawnedController = Cast<AAIController>(Enemy->GetController());
    Record.RuntimeId = Identity->EnsureRuntimeId();
    Record.Generation = Generation;
    Record.WaveIndex = WaveIndex;
    Record.SpawnOrdinal = Planned.SpawnOrdinal;
    OwnedEnemies.Add(Record);
    Brain->OnStateChanged.AddUniqueDynamic(this, &ANLEncounterController::HandleEnemyStateChanged);
    Enemy->OnDestroyed.AddUniqueDynamic(this, &ANLEncounterController::HandleOwnedEnemyDestroyed);
    ++RuntimeWaves[WaveIndex].NextPlanIndex;
    ++RuntimeWaves[WaveIndex].SpawnedCount;
    ++SpawnedCount;
    NextSpawnAt = GetEncounterTime() + RuntimeWaves[WaveIndex].SpawnIntervalSeconds;

    // ResetBrain preserves the authored spawn grace (0.35 seconds by default).
    // The identity and state listener exist before this can cause any transition.
    Brain->SpawnGraceSeconds = FMath::IsFinite(Brain->SpawnGraceSeconds)
        ? FMath::Max(0.35f, Brain->SpawnGraceSeconds) : 0.35f;
    Enemy->SetCombatEnabled(true);
    if (EncounterGeneration != Generation || !IsRunning()) return false;
    if (UNLAttackDirectorSubsystem* Director = GetWorld()->GetSubsystem<UNLAttackDirectorSubsystem>())
    {
        if (!Director->TryRegisterActiveFighter(Enemy))
        {
            UE_LOG(LogNLEncounter, Warning, TEXT("%s: spawned enemy could not join the active-fighter budget."), *GetName());
            ++FailedSpawnCount;
            FailEncounter(TEXT("SpawnFailed"));
            return false;
        }
    }
    else
    {
        ++FailedSpawnCount;
        FailEncounter(TEXT("SpawnFailed"));
        return false;
    }
    if (bEncounterPaused)
    {
        Enemy->SetLabPaused(true);
        Enemy->SetActorTickEnabled(false);
        Enemy->GetMesh()->SetComponentTickEnabled(false);
        Enemy->GetCharacterMovement()->SetComponentTickEnabled(false);
        if (AAIController* AI = Cast<AAIController>(Enemy->GetController())) AI->SetActorTickEnabled(false);
    }
    UE_LOG(LogNLEncounter, Log, TEXT("%s: combat spawned ordinal=%d wave=%d point=%s actor=%s capsule=%s hidden=%s"),
        *GetName(), Planned.SpawnOrdinal, WaveIndex, *Point.SpawnPointId.ToString(), *Enemy->GetName(),
        *Enemy->GetActorLocation().ToCompactString(), Enemy->IsHidden() ? TEXT("yes") : TEXT("no"));
    return true;
}

void ANLEncounterController::EvaluateWaveClear()
{
    if (bObjectiveSpawningStopped) return;
    if (!RuntimeWaves.IsValidIndex(CurrentWaveIndex) || bSpawnInProgress) return;
    const FRuntimeWave& Wave = RuntimeWaves[CurrentWaveIndex];
    if (Wave.NextPlanIndex < Wave.Plan.Num()) return;
    if (GetAliveCount() > 0)
    {
        SetState(ENLEncounterState::WaitingClear);
        return;
    }
    // A restored entry already includes every preceding wave. Advance this
    // wave once without replaying rewards or counting those waves again.
    CompletedWaveCount = FMath::Max(CompletedWaveCount, CurrentWaveIndex + 1);
    if (bDeferCompletionToObjective && CurrentWaveIndex + 1 >= RuntimeWaves.Num())
    {
        StopSpawningForObjective();
        return;
    }
    // A finished wave cannot leave hostile or reflected shots in the next entry.
    ANLCombatProjectile::DestroyEncounterProjectiles(this);
    if (CurrentWaveIndex + 1 < RuntimeWaves.Num())
    {
        IntermissionEndsAt = GetEncounterTime() + Wave.IntermissionSeconds;
        SetState(ENLEncounterState::Intermission);
        return;
    }
    const uint64 Generation = EncounterGeneration;
    SetState(ENLEncounterState::Completed);
    if (EncounterGeneration != Generation || State != ENLEncounterState::Completed || bTerminalOutcomeEmitted) return;
    bTerminalOutcomeEmitted = true;
    OnEncounterCompleted.Broadcast();
}

ANLEncounterController::FOwnedEnemy* ANLEncounterController::FindOwnedEnemy(const ANLEnemyCharacter* Enemy)
{
    return OwnedEnemies.FindByPredicate([this, Enemy](const FOwnedEnemy& Record)
    {
        return Record.Generation == EncounterGeneration && Record.Enemy.Get() == Enemy;
    });
}

const ANLEncounterController::FOwnedEnemy* ANLEncounterController::FindOwnedEnemy(const ANLEnemyCharacter* Enemy) const
{
    return OwnedEnemies.FindByPredicate([this, Enemy](const FOwnedEnemy& Record)
    {
        return Record.Generation == EncounterGeneration && Record.Enemy.Get() == Enemy;
    });
}

void ANLEncounterController::HandleEnemyStateChanged(AActor* EnemyActor, ENLEnemyState PreviousState, ENLEnemyState NewState)
{
    if (bCleaningUp || bEndingPlay || !IsRunning()) return;
    ANLEnemyCharacter* Enemy = Cast<ANLEnemyCharacter>(EnemyActor);
    FOwnedEnemy* Record = FindOwnedEnemy(Enemy);
    if (!Record || Record->Terminal != EOwnedTerminal::Active) return;
    if (!Enemy->CombatIdentity || Enemy->CombatIdentity->GetRuntimeId() != Record->RuntimeId)
    {
        Record->Terminal = EOwnedTerminal::Destroyed;
        FailEncounter(TEXT("EnemyRemoved"));
        return;
    }
    if (NewState == ENLEnemyState::Dead)
    {
        // A stable ordinal/runtime identity can produce only one defeat event.
        Record->Terminal = EOwnedTerminal::Defeated;
        const float Length = Enemy->DeathAnimation ? Enemy->DeathAnimation->GetPlayLength() : 0.0f;
        Record->CorpseExpiresAt = GetEncounterTime() + (IsValidDuration(Length) ? Length : 0.0f) + RuntimeCorpseHoldSeconds;
        ++DefeatedCount;
        const FGuid RuntimeId = Record->RuntimeId;
        const int32 Ordinal = Record->SpawnOrdinal;
        OnEnemyDefeated.Broadcast(Enemy, RuntimeId, Ordinal);
        // Evaluation happens in Tick, after all synchronous death listeners finish.
    }
    else if (NewState == ENLEnemyState::Despawn)
    {
        Record->Terminal = EOwnedTerminal::Despawned;
        UE_LOG(LogNLEncounter, Warning, TEXT("%s: owned enemy ordinal %d despawned before defeat (health %.1f)."),
            *GetName(), Record->SpawnOrdinal, Enemy->Vitals ? Enemy->Vitals->GetHealth() : -1.0f);
        FailEncounter(TEXT("NavigationFailed"));
    }
}

void ANLEncounterController::HandleOwnedEnemyDestroyed(AActor* EnemyActor)
{
    if (bCleaningUp || bEndingPlay) return;
    FOwnedEnemy* Record = FindOwnedEnemy(Cast<ANLEnemyCharacter>(EnemyActor));
    if (!Record || Record->Terminal != EOwnedTerminal::Active) return;
    Record->Terminal = EOwnedTerminal::Destroyed;
    if (IsRunning()) FailEncounter(TEXT("EnemyRemoved"));
}

void ANLEncounterController::AuditOwnedEnemies()
{
    const uint64 Generation = EncounterGeneration;
    for (int32 Index = 0; Index < OwnedEnemies.Num(); ++Index)
    {
        FOwnedEnemy& Record = OwnedEnemies[Index];
        if (Record.Generation != Generation || Record.Terminal != EOwnedTerminal::Active) continue;
        ANLEnemyCharacter* Enemy = Record.Enemy.Get();
        if (!IsValid(Enemy) || !Enemy->CombatIdentity || Enemy->CombatIdentity->GetRuntimeId() != Record.RuntimeId
            || !Enemy->GetEnemyBrain())
        {
            Record.Terminal = EOwnedTerminal::Destroyed;
            FailEncounter(TEXT("EnemyRemoved"));
            return;
        }
        const ENLEnemyState EnemyState = Enemy->GetEnemyBrain()->GetState();
        if (EnemyState == ENLEnemyState::Dead || EnemyState == ENLEnemyState::Despawn)
        {
            HandleEnemyStateChanged(Enemy, EnemyState, EnemyState);
            if (EncounterGeneration != Generation || !IsRunning()) return;
        }
    }
}

void ANLEncounterController::UnbindEnemy(ANLEnemyCharacter* Enemy)
{
    if (!Enemy) return;
    if (UNLEnemyBrainComponent* Brain = Enemy->GetEnemyBrain())
        Brain->OnStateChanged.RemoveDynamic(this, &ANLEncounterController::HandleEnemyStateChanged);
    Enemy->OnDestroyed.RemoveDynamic(this, &ANLEncounterController::HandleOwnedEnemyDestroyed);
}

void ANLEncounterController::CleanupExpiredCorpses()
{
    const uint64 Generation = EncounterGeneration;
    const double Now = GetEncounterTime();
    for (int32 Index = OwnedEnemies.Num() - 1; Index >= 0; --Index)
    {
        FOwnedEnemy& Record = OwnedEnemies[Index];
        if (Record.Generation != Generation || Record.Terminal != EOwnedTerminal::Defeated
            || (Record.Enemy.IsValid() && Now < Record.CorpseExpiresAt)) continue;
        ANLEnemyCharacter* Enemy = Record.Enemy.Get();
        AAIController* AI = Record.SpawnedController.Get();
        // Presentation may start on a later safe tick; even a zero hold must
        // allow the pending/playing death clip to finish before retirement.
        if (Enemy && Enemy->IsDeathPresentationInProgress()) continue;
        UnbindEnemy(Enemy);
        Record.Enemy.Reset();
        Record.SpawnedController.Reset();
        if (Enemy) Enemy->Destroy();
        if (IsValid(AI)) AI->Destroy();
        if (EncounterGeneration != Generation || bEndingPlay) return;
        // Totals live in the cumulative counters; retired actor handles need no scan.
        OwnedEnemies.RemoveAt(Index, 1, EAllowShrinking::No);
    }
}

void ANLEncounterController::CleanupOwnedEnemies()
{
    if (bCleaningUp) return;
    bCleaningUp = true;
    CleanupReadyPreviews();
    ANLCombatProjectile::DestroyEncounterProjectiles(this);
    // Generation has already advanced; no record is eligible for a new reward.
    for (FOwnedEnemy& Record : OwnedEnemies)
    {
        ANLEnemyCharacter* Enemy = Record.Enemy.Get();
        AAIController* AI = Record.SpawnedController.Get();
        Record.Terminal = EOwnedTerminal::CleanedUp;
        if (Enemy)
        {
            UnbindEnemy(Enemy);
            Enemy->SetCombatEnabled(false);
            if (UNLEnemyBrainComponent* Brain = Enemy->GetEnemyBrain()) Brain->Despawn();
            Enemy->Destroy();
        }
        if (IsValid(AI)) AI->Destroy();
        Record.Enemy.Reset();
        Record.SpawnedController.Reset();
    }
    bCleaningUp = false;
}

void ANLEncounterController::StopOwnedEnemies()
{
    const uint64 Generation = EncounterGeneration;
    TArray<TWeakObjectPtr<ANLEnemyCharacter>> Enemies;
    for (const FOwnedEnemy& Record : OwnedEnemies) Enemies.Add(Record.Enemy);
    for (const TWeakObjectPtr<ANLEnemyCharacter>& WeakEnemy : Enemies)
    {
        if (EncounterGeneration != Generation) return;
        if (ANLEnemyCharacter* Enemy = WeakEnemy.Get())
        {
            Enemy->SetCombatEnabled(false);
            Enemy->SetLabPaused(true);
            Enemy->GetCharacterMovement()->SetComponentTickEnabled(false);
            if (AAIController* AI = Cast<AAIController>(Enemy->GetController())) AI->SetActorTickEnabled(false);
        }
    }
}

void ANLEncounterController::SetState(ENLEncounterState NewState)
{
    if (State == NewState) return;
    const ENLEncounterState PreviousState = State;
    State = NewState;
    if (State != ENLEncounterState::Ready && State != ENLEncounterState::Cancelled) CleanupReadyPreviews();
    if (!bEndingPlay) OnStateChanged.Broadcast(PreviousState, NewState);
}
