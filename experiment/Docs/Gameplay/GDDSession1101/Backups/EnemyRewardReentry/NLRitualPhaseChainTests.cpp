#if WITH_DEV_AUTOMATION_TESTS

#include "AI/NLEnemyCharacter.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Components/SceneComponent.h"
#include "CoreGlobals.h"
#include "Encounter/NLEncounterController.h"
#include "Encounter/NLLevelEncounterDirector.h"
#include "Encounter/NLWaveDefinition.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/WorldSettings.h"
#include "HAL/PlatformFileManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/Paths.h"
#include "Objective/NLRitualObjective.h"
#include "Progression/NLRunStateSubsystem.h"
#include "Progression/NLUpgradeDefinition.h"
#include "Tests/NLRunCallbackTestListener.h"
#include <limits>

namespace NLRitualPhaseTests
{
    constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
    const FName ObjectiveId(TEXT("Objective.Test.FourPhases"));
    const FName PhaseIds[] = {TEXT("Establish"), TEXT("Interrupt"), TEXT("Siege"), TEXT("Unseal")};

    /** Native logic world with genuine Director/Encounter lifecycle, isolated from authored maps and profiles. */
    struct FWorld
    {
        UWorld* World = nullptr;
        UGameInstance* Instance = nullptr;
        UNLRunStateSubsystem* Run = nullptr;
        APawn* Player = nullptr;
        ANLRitualObjective* Objective = nullptr;
        ANLLevelEncounterDirector* Director = nullptr;
        UNLUpgradeDefinition* UpgradeDefinition = nullptr;
        TArray<FGuid> OwnedRuns;
        const uint64 SavedFrame = GFrameCounter;

        explicit FWorld(bool bWithRun = false)
        {
            if (!GEngine) return;
            const UWorld::InitializationValues Values = UWorld::InitializationValues()
                .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true)
                .ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateNavigation(false).CreateAISystem(false);
            World = UWorld::CreateWorld(EWorldType::Game, false,
                FName(*FString::Printf(TEXT("RitualPhases_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Digits))),
                nullptr, true, ERHIFeatureLevel::Num, &Values);
            if (!World) return;
            FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
            Context.SetCurrentWorld(World);
            if (bWithRun)
            {
                Instance = NewObject<UGameInstance>(GEngine);
                World->SetGameInstance(Instance);
                Context.OwningGameInstance = Instance;
                Instance->Init();
                Run = Instance->GetSubsystem<UNLRunStateSubsystem>();
                NewRun();
            }
            World->InitializeActorsForPlay(FURL());
            World->BeginPlay();
            World->GetWorldSettings()->NotifyBeginPlay();
            Player = AddPawn(ENLCombatFaction::Player);
            Objective = World->SpawnActorDeferred<ANLRitualObjective>(ANLRitualObjective::StaticClass(),
                FTransform(FVector(1000, 0, 0)), nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
            if (Objective)
            {
                Objective->ObjectiveStableId = ObjectiveId;
                Objective->bStartActive = false;
                Objective->EffectiveRescueSeconds = 240.0f;
                Objective->FinishSpawning(FTransform(FVector(1000, 0, 0)));
            }
        }
        ~FWorld()
        {
            if (World)
            {
                World->EndPlay(EEndPlayReason::Quit);
                GEngine->DestroyWorldContext(World);
                World->DestroyWorld(false);
            }
            if (Instance) Instance->Shutdown();
            // Only fresh fixture-owned GUID ledgers are eligible for cleanup; no main profile is opened.
            IPlatformFile& Files = FPlatformFileManager::Get().GetPlatformFile();
            for (const FGuid Id : OwnedRuns)
            {
                const FString Path = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(),
                    TEXT("SaveGames/NilinMasterRewards"), Id.ToString(EGuidFormats::Digits) + TEXT(".nlmr")));
                Files.DeleteFile(*Path);
                Files.DeleteFile(*(Path + TEXT(".tmp")));
            }
            GFrameCounter = SavedFrame;
        }
        void NewRun()
        {
            if (!Run) return;
            const FGuid Id = FGuid::NewGuid();
            OwnedRuns.Add(Id);
            Run->BeginRun(Id);
        }
        APawn* AddPawn(ENLCombatFaction Faction)
        {
            APawn* Pawn = World->SpawnActor<APawn>();
            if (!Pawn) return nullptr;
            USceneComponent* Root = NewObject<USceneComponent>(Pawn);
            Pawn->SetRootComponent(Root); Pawn->AddInstanceComponent(Root); Root->RegisterComponent();
            UNLCombatIdentityComponent* Identity = NewObject<UNLCombatIdentityComponent>(Pawn);
            Identity->Faction = Faction; Pawn->AddInstanceComponent(Identity); Identity->RegisterComponent();
            Identity->EnsureRuntimeId();
            UNLCombatVitalsComponent* Vitals = NewObject<UNLCombatVitalsComponent>(Pawn);
            Vitals->DamageProtectionSeconds = 0.0f; Pawn->AddInstanceComponent(Vitals); Vitals->RegisterComponent();
            Vitals->ResetVitals();
            return Pawn;
        }
        TArray<FNLLevelEncounterStage> Stages()
        {
            TArray<FNLLevelEncounterStage> Result;
            for (int32 Index = 0; Index < 4; ++Index)
            {
                FNLLevelEncounterStage Stage;
                Stage.StageId = PhaseIds[Index]; Stage.RequiredStageId = Index ? PhaseIds[Index - 1] : NAME_None;
                Stage.ObjectiveStableId = ObjectiveId; Stage.ObjectiveProgressTarget = (Index + 1) * 25.0f;
                Stage.bContinueObjectiveFromPreviousStage = Index > 0;
                Stage.WarningSeconds = 0.0f; Stage.TriggerExtent = FVector(100);
                FNLWaveSpawnPoint Point; Point.SpawnPointId = TEXT("Point");
                Point.SpawnTransform = FTransform(FVector(2000, 0, 100)); Stage.SpawnPoints.Add(Point);
                UNLWaveDefinition* Wave = NewObject<UNLWaveDefinition>(World);
                Wave->WaveId = FName(*FString::Printf(TEXT("Wave.%d"), Index));
                FNLWaveSpawnEntry Entry; Entry.EntryId = TEXT("Enemy"); Entry.EnemyClass = ANLEnemyCharacter::StaticClass();
                Entry.Count = 2; Entry.SpawnPointIds.Add(Point.SpawnPointId); Wave->SpawnEntries.Add(Entry);
                Stage.Waves.Add(Wave); Result.Add(Stage);
            }
            return Result;
        }
        bool Setup(const TArray<FNLLevelEncounterStage>* Override = nullptr)
        {
            if (!World || !Objective || !Player) return false;
            Director = World->SpawnActorDeferred<ANLLevelEncounterDirector>(ANLLevelEncounterDirector::StaticClass(),
                FTransform::Identity, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
            if (!Director) return false;
            Director->Stages = Override ? *Override : Stages();
            Director->UpgradeDefinition = UpgradeDefinition;
            Director->FinishSpawning(FTransform::Identity);
            return true;
        }
        bool Start(int32 Index)
        {
            if (!Director->TryActivateStage(PhaseIds[Index], Player)) return false;
            Director->Tick(0.0f);
            return Director->GetStageStatus(PhaseIds[Index]) == ENLLevelStageState::Active;
        }
        void FinishCurrent()
        {
            Objective->Tick(60.0f);
            ++GFrameCounter;
            Objective->Tick(.01f);
        }
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLRitualFourPhasesTest,
    "Nilin.LevelEncounter.RitualPhases.SharedProgressIntegrityAndOneFinalRescue", NLRitualPhaseTests::Flags)
bool FNLRitualFourPhasesTest::RunTest(const FString& Parameters)
{
    using namespace NLRitualPhaseTests;
    FWorld F;
    if (!TestTrue(TEXT("Fixture ready"), F.Setup())) return false;
    for (int32 Index = 0; Index < 4; ++Index)
    {
        if (!TestTrue(TEXT("Required phase can start"), F.Start(Index))) return false;
        TestEqual(TEXT("Entrance progress carries the prior quarter"), F.Objective->GetRescueProgress(), Index * 25.0f);
        TestEqual(TEXT("No free integrity refill between phases"), F.Objective->GetIntegrity(), 100.0f - Index * 7.0f);
        TestEqual(TEXT("Entrance retry snapshot stores carried progress"), F.Director->GetRetryObjectiveSnapshot().RescueProgress, Index * 25.0f);
        TestEqual(TEXT("Target is the next quarter"), F.Objective->GetProgressTarget(), (Index + 1) * 25.0f);
        F.Objective->Vitals->ApplyCombatDamage(7.0f);
        APawn* Threat = F.AddPawn(ENLCombatFaction::Enemy);
        TestTrue(TEXT("A genuine living threat delays the phase boundary"), F.Objective->RegisterRemainingThreat(TEXT("Threat"), Threat));
        F.Objective->Tick(60.0f);
        TestEqual(TEXT("Sixty effective seconds add one quarter of the 240-second rescue"), F.Objective->GetRescueProgress(), (Index + 1) * 25.0f);
        TestTrue(TEXT("Every phase has the same remaining-threat gate"), F.Objective->IsCompletionPending());
        TestTrue(TEXT("Threshold stops all later spawn work"), F.Director->GetActiveEncounter()->IsSpawningStoppedForObjective());
        ++GFrameCounter;
        F.Objective->Tick(240.0f);
        TestEqual(TEXT("Pending time cannot overrun the phase ceiling"), F.Objective->GetRescueProgress(), (Index + 1) * 25.0f);
        TestEqual(TEXT("Live threat keeps stage active"), F.Director->GetStageStatus(PhaseIds[Index]), ENLLevelStageState::Active);
        Threat->FindComponentByClass<UNLCombatVitalsComponent>()->ApplyCombatDamage(1000.0f);
        F.Objective->Tick(.01f);
        TestEqual(TEXT("Threat clear completes only current stage"), F.Director->GetStageStatus(PhaseIds[Index]), ENLLevelStageState::Completed);
        TestEqual(TEXT("Only fourth phase emits final rescue"), F.Objective->GetCompletionEventCount(), Index == 3 ? 1 : 0);
        TestEqual(TEXT("Intermediate phase completion count"), F.Objective->GetPhaseCompletionEventCount(), FMath::Min(Index + 1, 3));
        TestEqual(TEXT("Distinct terminal state below 100"), F.Objective->IsPhaseCompleted(), Index < 3);
        F.Objective->Tick(240.0f);
        TestEqual(TEXT("Completed phase remains bounded until successor begins"), F.Objective->GetRescueProgress(), (Index + 1) * 25.0f);
    }
    TestTrue(TEXT("Final rescue is complete"), F.Objective->IsRescueCompleted());
    TestEqual(TEXT("All four stages cleared"), F.Director->GetCompletedStageCount(), 4);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLRitualPhaseRetryTest,
    "Nilin.LevelEncounter.RitualPhases.PauseInterferenceAndRetryKeepPhaseEntrance", NLRitualPhaseTests::Flags)
bool FNLRitualPhaseRetryTest::RunTest(const FString& Parameters)
{
    using namespace NLRitualPhaseTests;
    FWorld F;
    if (!TestTrue(TEXT("First phase starts"), F.Setup() && F.Start(0))) return false;
    F.Objective->Vitals->ApplyCombatDamage(10.0f);
    F.FinishCurrent();
    if (!TestTrue(TEXT("Second phase starts"), F.Start(1))) return false;
    for (int32 Attempt = 0; Attempt < 3; ++Attempt)
    {
        ANLEncounterController* Old = F.Director->GetActiveEncounter();
        Old->SetEncounterPaused(true); F.Objective->Tick(100.0f);
        TestEqual(TEXT("Pause adds no rescue"), F.Objective->GetRescueProgress(), 25.0f);
        Old->SetEncounterPaused(false);
        APawn* Source = F.AddPawn(ENLCombatFaction::Enemy);
        TestTrue(TEXT("Live source registers"), F.Objective->RegisterInterferenceSource(TEXT("Source"), Source));
        F.Objective->Tick(100.0f);
        TestEqual(TEXT("Interference adds no rescue"), F.Objective->GetRescueProgress(), 25.0f);
        TestTrue(TEXT("Interrupt removes its source"), F.Objective->UnregisterInterferenceSource(TEXT("Source")));
        F.Objective->Tick(24.0f);
        TestEqual(TEXT("Progress resumes after interruption"), F.Objective->GetRescueProgress(), 35.0f);
        F.Objective->Vitals->ApplyCombatDamage(1000.0f);
        TestEqual(TEXT("Integrity failure belongs to current phase"), F.Director->GetStageStatus(PhaseIds[1]), ENLLevelStageState::Failed);
        TestTrue(TEXT("Native phase retry succeeds"), F.Director->RetryActiveStage());
        TestTrue(TEXT("Old encounter discarded"), Old->IsActorBeingDestroyed());
        TestEqual(TEXT("Retry returns to carried entry, never zero"), F.Objective->GetRescueProgress(), 25.0f);
        TestEqual(TEXT("Retry restores entry integrity, never full"), F.Objective->GetIntegrity(), 90.0f);
        TestEqual(TEXT("Prior phase stays cleared"), F.Director->GetStageStatus(PhaseIds[0]), ENLLevelStageState::Completed);
        TestEqual(TEXT("Future phase remains locked"), F.Director->GetStageStatus(PhaseIds[2]), ENLLevelStageState::Locked);
        TestEqual(TEXT("No failed-phase source survives"), F.Objective->GetInterferenceSourceCount(), 0);
        F.Director->Tick(0.0f);
        Source->Destroy();
    }
    // Failure wins even on a quarter-progress candidate, just as it does at final 100 percent.
    F.Objective->Tick(60.0f);
    F.Objective->Vitals->ApplyCombatDamage(1000.0f);
    ++GFrameCounter; F.Objective->Tick(.01f);
    TestEqual(TEXT("Same-frame integrity zero cannot clear intermediate phase"), F.Director->GetStageStatus(PhaseIds[1]), ENLLevelStageState::Failed);
    TestEqual(TEXT("Only original first-phase completion emitted"), F.Objective->GetPhaseCompletionEventCount(), 1);
    TestEqual(TEXT("No early final rescue"), F.Objective->GetCompletionEventCount(), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLRitualPhaseSnapshotTest,
    "Nilin.LevelEncounter.RitualPhases.SnapshotValidationAndLegacyDefault", NLRitualPhaseTests::Flags)
bool FNLRitualPhaseSnapshotTest::RunTest(const FString& Parameters)
{
    using namespace NLRitualPhaseTests;
    FWorld F;
    if (!TestNotNull(TEXT("Objective"), F.Objective)) return false;
    FNLObjectiveSnapshot Snapshot = F.Objective->CaptureObjectiveSnapshot();
    Snapshot.RescueProgress = 25.0f; Snapshot.Integrity = 81.0f;
    TestTrue(TEXT("Intermediate snapshot can start next phase"), F.Objective->RestoreObjectivePhaseSnapshot(Snapshot, 50.0f));
    for (float Invalid : {0.0f, 24.0f, 101.0f, std::numeric_limits<float>::quiet_NaN()})
    {
        TestFalse(TEXT("Invalid phase ceiling rejected"), F.Objective->RestoreObjectivePhaseSnapshot(Snapshot, Invalid));
        TestEqual(TEXT("Rejected ceiling preserves live progress"), F.Objective->GetRescueProgress(), 25.0f);
        TestEqual(TEXT("Rejected ceiling preserves integrity"), F.Objective->GetIntegrity(), 81.0f);
        TestEqual(TEXT("Rejected ceiling preserves target"), F.Objective->GetProgressTarget(), 50.0f);
    }
    TestTrue(TEXT("Existing standalone restore remains supported"), F.Objective->RestoreObjectiveSnapshot(Snapshot));
    TestEqual(TEXT("Legacy restore restores full-rescue target"), F.Objective->GetProgressTarget(), 100.0f);
    F.Objective->Tick(240.0f); ++GFrameCounter; F.Objective->Tick(.01f);
    TestTrue(TEXT("Standalone restore still reaches final rescue"), F.Objective->IsRescueCompleted());
    TestEqual(TEXT("Standalone path emits no intermediate completion"), F.Objective->GetPhaseCompletionEventCount(), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLRitualPhaseNewRunTest,
    "Nilin.LevelEncounter.RitualPhases.NewRunDiscardsCommittedBoundaries", NLRitualPhaseTests::Flags)
bool FNLRitualPhaseNewRunTest::RunTest(const FString& Parameters)
{
    using namespace NLRitualPhaseTests;
    FWorld F(true);
    if (!TestNotNull(TEXT("Isolated run subsystem"), F.Run) || !TestTrue(TEXT("First phase starts"), F.Setup() && F.Start(0))) return false;
    F.Objective->Vitals->ApplyCombatDamage(23.0f); F.FinishCurrent();
    TestTrue(TEXT("Second phase receives committed boundary"), F.Start(1));
    TestEqual(TEXT("Second phase receives damaged integrity"), F.Objective->GetIntegrity(), 77.0f);
    F.NewRun();
    TestEqual(TEXT("New run resets all stages"), F.Director->GetCompletedStageCount(), 0);
    TestTrue(TEXT("New run has no active stage"), F.Director->GetActiveStageId().IsNone());
    TestFalse(TEXT("Prior-run boundary cannot skip the first stage"), F.Director->TryActivateStage(PhaseIds[1], F.Player));
    TestTrue(TEXT("New run starts fresh first phase"), F.Start(0));
    TestEqual(TEXT("Old progress is not carried into new run"), F.Objective->GetRescueProgress(), 0.0f);
    TestEqual(TEXT("New run gets its genuine initial integrity"), F.Objective->GetIntegrity(), 100.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLRitualPhaseIdentityTest,
    "Nilin.LevelEncounter.RitualPhases.InvalidSequenceAndChangedObjectiveFailClosed", NLRitualPhaseTests::Flags)
bool FNLRitualPhaseIdentityTest::RunTest(const FString& Parameters)
{
    using namespace NLRitualPhaseTests;
    {
        FWorld F;
        TArray<FNLLevelEncounterStage> Stages = F.Stages();
        Stages[1].ObjectiveProgressTarget = 25.0f;
        AddExpectedError(TEXT("InvalidObjectivePhaseSequence"), EAutomationExpectedErrorFlags::Contains, 1);
        if (!TestTrue(TEXT("Invalid configuration fixture created"), F.Setup(&Stages))) return false;
        TestFalse(TEXT("Non-increasing phase sequence rejected before play"), F.Director->TryActivateStage(PhaseIds[0], F.Player));
        TestNull(TEXT("Invalid sequence creates no encounter"), F.Director->GetActiveEncounter());
    }
    {
        FWorld F;
        if (!TestTrue(TEXT("Valid first phase"), F.Setup() && F.Start(0))) return false;
        F.FinishCurrent();
        F.Objective->Destroy();
        ANLRitualObjective* Replacement = F.World->SpawnActorDeferred<ANLRitualObjective>(ANLRitualObjective::StaticClass(),
            FTransform::Identity, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
        Replacement->ObjectiveStableId = ObjectiveId; Replacement->bStartActive = false;
        Replacement->FinishSpawning(FTransform::Identity);
        TestFalse(TEXT("A same-ID replacement cannot inherit another actor's completed phase"), F.Director->TryActivateStage(PhaseIds[1], F.Player));
        TestEqual(TEXT("Replacement failure gives precise reason"), F.Director->GetEntryBlockReason(), FName(TEXT("MissingCompletedObjectivePhase")));
        TestEqual(TEXT("Rejected replacement remains untouched"), Replacement->GetRescueProgress(), 0.0f);
    }
    {
        FWorld F;
        if (!TestTrue(TEXT("Callback fixture ready"), F.Setup())) return false;
        FScriptDelegate DestroyOnPhase;
        DestroyOnPhase.BindUFunction(F.Objective, TEXT("K2_DestroyActor"));
        // Install before the Director binds its handler during entry, so this genuinely
        // invalidates the actor before the Director receives the synchronous phase event.
        F.Objective->OnPhaseCompleted.Add(DestroyOnPhase);
        if (!TestTrue(TEXT("Callback fixture starts"), F.Start(0))) return false;
        F.FinishCurrent(); F.Director->Tick(.1f);
        TestEqual(TEXT("Destroyed objective fails instead of committing a stale boundary"), F.Director->GetStageStatus(PhaseIds[0]), ENLLevelStageState::Failed);
        TestEqual(TEXT("Next phase remains locked after callback invalidation"), F.Director->GetStageStatus(PhaseIds[1]), ENLLevelStageState::Locked);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLRitualPhaseStartNewRunTest,
    "Nilin.LevelEncounter.RitualPhases.ActiveNotificationNewRunCannotResumeStaleEncounter", NLRitualPhaseTests::Flags)
bool FNLRitualPhaseStartNewRunTest::RunTest(const FString& Parameters)
{
    using namespace NLRitualPhaseTests;
    FWorld F(true);
    if (!TestNotNull(TEXT("Run subsystem"), F.Run) || !TestTrue(TEXT("Fixture ready"), F.Setup())) return false;
    UNLRunCallbackTestListener* Listener = NewObject<UNLRunCallbackTestListener>(F.Director);
    TWeakObjectPtr<ANLEncounterController> PreviousEncounter;
    bool bObservedActive = false;
    const FGuid BeforeRun = F.Run->GetRunId();
    Listener->StageCallback = [&](FName StageId, ENLLevelStageState State)
    {
        if (State != ENLLevelStageState::Active || StageId != PhaseIds[0]) return;
        bObservedActive = true;
        F.Director->OnStageChanged.RemoveDynamic(Listener, &UNLRunCallbackTestListener::HandleStageChanged);
        PreviousEncounter = F.Director->GetActiveEncounter();
        F.NewRun(); // Real synchronous run-state event clears the Director during its Active broadcast.
    };
    F.Director->OnStageChanged.AddDynamic(Listener, &UNLRunCallbackTestListener::HandleStageChanged);
    if (!TestTrue(TEXT("Stage first enters warning"), F.Director->TryActivateStage(PhaseIds[0], F.Player))) return false;
    F.Director->Tick(0.0f);
    TestTrue(TEXT("Real Active stage callback fired"), bObservedActive);
    TestTrue(TEXT("Callback began another run"), F.Run->GetRunId() != BeforeRun);
    TestTrue(TEXT("Old startup encounter was torn down"), !PreviousEncounter.IsValid() || PreviousEncounter->IsActorBeingDestroyed());
    TestTrue(TEXT("Old start cannot repopulate the new run's active stage"), F.Director->GetActiveStageId().IsNone());
    TestNull(TEXT("Old start cannot reactivate its destroyed encounter"), F.Director->GetActiveEncounter());
    TestEqual(TEXT("First stage is available in the new run"), F.Director->GetStageStatus(PhaseIds[0]), ENLLevelStageState::Available);
    TestTrue(TEXT("Old startup does not fail the new run"), F.Director->GetFailureReason().IsNone());
    F.Objective->Tick(60.0f);
    TestEqual(TEXT("Old start did not reactivate the ritual"), F.Objective->GetRescueProgress(), 0.0f);
    TestTrue(TEXT("New run can enter first stage normally"), F.Start(0));
    F.Objective->Tick(24.0f);
    TestEqual(TEXT("New encounter progresses normally after reentrant reset"), F.Objective->GetRescueProgress(), 10.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLRitualPhaseCompleteNewRunTest,
    "Nilin.LevelEncounter.RitualPhases.CompletionUpgradeCallbackCannotCompleteNewRun", NLRitualPhaseTests::Flags)
bool FNLRitualPhaseCompleteNewRunTest::RunTest(const FString& Parameters)
{
    using namespace NLRitualPhaseTests;
    FWorld F(true);
    if (!TestNotNull(TEXT("Isolated run"), F.Run)) return false;
    F.UpgradeDefinition = NewObject<UNLUpgradeDefinition>(F.World);
    TArray<FNLLevelEncounterStage> Stages = F.Stages();
    Stages[0].MinimumUpgradeLevelOnComplete = 2;
    if (!TestTrue(TEXT("Phase with authored upgrade floor starts"), F.Setup(&Stages) && F.Start(0))) return false;
    UNLRunCallbackTestListener* Listener = NewObject<UNLRunCallbackTestListener>(F.Director);
    const FGuid BeforeRun = F.Run->GetRunId();
    bool bObservedUpgrade = false;
    Listener->Callback = [&]()
    {
        if (F.Run->GetProgressionState().UpgradeLevel != 2) return;
        bObservedUpgrade = true;
        F.Run->OnRunStateChanged.RemoveDynamic(Listener, &UNLRunCallbackTestListener::HandleRunChanged);
        F.NewRun(); // EnsureUpgradeLevel's real broadcast invalidates the old phase completion.
    };
    F.Run->OnRunStateChanged.AddDynamic(Listener, &UNLRunCallbackTestListener::HandleRunChanged);
    F.FinishCurrent();
    TestTrue(TEXT("Completion used the real upgrade-floor callback"), bObservedUpgrade);
    TestTrue(TEXT("Upgrade observer started a different run"), F.Run->GetRunId() != BeforeRun);
    TestEqual(TEXT("Stale phase completion cannot mark new-run stage completed"), F.Director->GetCompletedStageCount(), 0);
    TestEqual(TEXT("First phase remains available after callback reset"), F.Director->GetStageStatus(PhaseIds[0]), ENLLevelStageState::Available);
    TestTrue(TEXT("New run has no active old stage"), F.Director->GetActiveStageId().IsNone());
    TestNull(TEXT("Old encounter is gone"), F.Director->GetActiveEncounter());
    TestEqual(TEXT("New run keeps its own baseline level"), F.Run->GetProgressionState().UpgradeLevel, 1);
    TestTrue(TEXT("Old completion does not fail the new run"), F.Director->GetFailureReason().IsNone());
    TestTrue(TEXT("Fresh first phase remains playable"), F.Start(0));
    TestEqual(TEXT("Fresh phase gets no old completion progress"), F.Objective->GetRescueProgress(), 0.0f);
    return true;
}

#endif
