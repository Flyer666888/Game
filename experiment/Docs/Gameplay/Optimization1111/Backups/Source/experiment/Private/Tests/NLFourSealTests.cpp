#if WITH_DEV_AUTOMATION_TESTS

#include "AI/NLEnemyCharacter.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Components/SceneComponent.h"
#include "CoreGlobals.h"
#include "Encounter/NLLevelEncounterDirector.h"
#include "Encounter/NLWaveDefinition.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/WorldSettings.h"
#include "HAL/PlatformFileManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"
#include "Progression/NLRunStateSubsystem.h"
#include "Tests/NLRunCallbackTestListener.h"

namespace NLFourSealTests
{
    constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
    const FName Masters[] = {TEXT("GM01"), TEXT("GM02"), TEXT("GM03"), TEXT("GM04")};
    const FName Seals[] = {TEXT("SwordSeal"), TEXT("TalismanSeal"), TEXT("AlchemySeal"), TEXT("WindSeal")};

    FString MarkerPath(FName LevelId)
    {
        const FString Name = LevelId.ToString().ToLower();
        const FTCHARToUTF8 Utf8(*Name);
        FSHAHash Hash;
        FSHA1::HashBuffer(Utf8.Get(), Utf8.Length(), Hash.Hash);
        return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(),
            TEXT("SaveGames/NilinLevelRuns"), Hash.ToString() + TEXT(".nlrun")));
    }

    void DeleteLedger(FGuid Id)
    {
        if (!Id.IsValid()) return;
        const FString Path = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(),
            TEXT("SaveGames/NilinMasterRewards"), Id.ToString(EGuidFormats::Digits) + TEXT(".nlmr")));
        FPlatformFileManager::Get().GetPlatformFile().DeleteFile(*Path);
        FPlatformFileManager::Get().GetPlatformFile().DeleteFile(*(Path + TEXT(".tmp")));
    }

    struct FRunCleanup
    {
        TArray<FGuid> Runs;
        TArray<FName> Levels;
        ~FRunCleanup()
        {
            for (FGuid Id : Runs) DeleteLedger(Id);
            for (FName Id : Levels)
            {
                const FString Path = MarkerPath(Id);
                FPlatformFileManager::Get().GetPlatformFile().DeleteFile(*Path);
                FPlatformFileManager::Get().GetPlatformFile().DeleteFile(*(Path + TEXT(".tmp")));
            }
        }
        FGuid AddRun() { const FGuid Id = FGuid::NewGuid(); Runs.Add(Id); return Id; }
        FName AddLevel()
        {
            const FName Id(*FString::Printf(TEXT("Test.FourSeals.%s"), *FGuid::NewGuid().ToString(EGuidFormats::Digits)));
            Levels.Add(Id);
            return Id;
        }
    };

    struct FScopedWorld
    {
        UWorld* World = nullptr;
        UGameInstance* Instance = nullptr;
        UNLRunStateSubsystem* Run = nullptr;
        FRunCleanup Cleanup;
        const uint64 SavedFrameCounter = GFrameCounter;
        FScopedWorld()
        {
            if (!GEngine) return;
            const UWorld::InitializationValues Values = UWorld::InitializationValues()
                .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true)
                .ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateNavigation(false).CreateAISystem(false);
            World = UWorld::CreateWorld(EWorldType::Game, false,
                FName(*FString::Printf(TEXT("FourSealGate_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Digits))),
                nullptr, true, ERHIFeatureLevel::Num, &Values);
            if (!World) return;
            Instance = NewObject<UGameInstance>(GEngine);
            World->SetGameInstance(Instance);
            FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
            Context.SetCurrentWorld(World);
            Context.OwningGameInstance = Instance;
            Instance->Init();
            Run = Instance->GetSubsystem<UNLRunStateSubsystem>();
            if (Run) Run->BeginRun(Cleanup.AddRun());
            World->InitializeActorsForPlay(FURL());
            World->BeginPlay();
            if (AWorldSettings* Settings = World->GetWorldSettings()) Settings->NotifyBeginPlay();
        }
        ~FScopedWorld()
        {
            if (World)
            {
                World->EndPlay(EEndPlayReason::Quit);
                GEngine->DestroyWorldContext(World);
                World->DestroyWorld(false);
            }
            if (Instance) Instance->Shutdown();
            GFrameCounter = SavedFrameCounter;
        }
        APawn* AddPlayer()
        {
            APawn* Pawn = World->SpawnActor<APawn>();
            if (!Pawn) return nullptr;
            USceneComponent* Root = NewObject<USceneComponent>(Pawn);
            Pawn->SetRootComponent(Root);
            Pawn->AddInstanceComponent(Root);
            Root->RegisterComponent();
            UNLCombatIdentityComponent* Identity = NewObject<UNLCombatIdentityComponent>(Pawn);
            Identity->Faction = ENLCombatFaction::Player;
            Pawn->AddInstanceComponent(Identity);
            Identity->RegisterComponent();
            Identity->EnsureRuntimeId();
            UNLCombatVitalsComponent* Vitals = NewObject<UNLCombatVitalsComponent>(Pawn);
            Pawn->AddInstanceComponent(Vitals);
            Vitals->RegisterComponent();
            Vitals->ResetVitals();
            return Pawn;
        }
        FNLLevelEncounterStage Stage(FName Id)
        {
            FNLLevelEncounterStage Result;
            Result.StageId = Id;
            Result.WarningSeconds = 20.0f;
            Result.TriggerExtent = FVector(100.0);
            FNLWaveSpawnPoint Point;
            Point.SpawnPointId = TEXT("Test.Point");
            Point.SpawnTransform.SetLocation(FVector(400, 0, 100));
            Result.SpawnPoints.Add(Point);
            UNLWaveDefinition* Wave = NewObject<UNLWaveDefinition>(World);
            Wave->WaveId = FName(*(Id.ToString() + TEXT(".Wave")));
            FNLWaveSpawnEntry Entry;
            Entry.EntryId = TEXT("Test.Enemy");
            Entry.EnemyClass = ANLEnemyCharacter::StaticClass();
            Entry.Count = 1;
            Entry.SpawnPointIds.Add(Point.SpawnPointId);
            Wave->SpawnEntries.Add(Entry);
            Result.Waves.Add(Wave);
            return Result;
        }
        ANLLevelEncounterDirector* AddDirector()
        {
            ANLLevelEncounterDirector* Director = World->SpawnActorDeferred<ANLLevelEncounterDirector>(
                ANLLevelEncounterDirector::StaticClass(), FTransform::Identity, nullptr, nullptr,
                ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
            if (!Director) return nullptr;
            for (int32 Index = 0; Index < 4; ++Index)
            {
                FNLLevelEncounterStage Master = Stage(Masters[Index]);
                Master.MasterId = Masters[Index];
                Master.SealId = Seals[Index];
                Master.TriggerCenter = FVector(1000 * (Index + 1), 0, 0);
                Director->Stages.Add(Master);
            }
            FNLLevelEncounterStage Boss = Stage(TEXT("Boss"));
            Boss.RequiredStageId = TEXT("GM04");
            for (FName Id : Seals) Boss.RequiredSealIds.Add(Id);
            Director->Stages.Add(Boss);
            Director->FinishSpawning(FTransform::Identity);
            return Director;
        }
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLFourSealOwnershipTest,
    "Nilin.Progression.FourSeals.AutomaticCollectionIndependentOfHealing", NLFourSealTests::Flags)
bool FNLFourSealOwnershipTest::RunTest(const FString& Parameters)
{
    using namespace NLFourSealTests;
    FRunCleanup Cleanup;
    UGameInstance* Outer = NewObject<UGameInstance>();
    UNLRunStateSubsystem* State = NewObject<UNLRunStateSubsystem>(Outer);
    State->BeginRun(Cleanup.AddRun());
    TestFalse(TEXT("Unknown identities cannot create a quest item"), State->GrantMasterSeal(TEXT("GM05"), TEXT("SwordSeal"), FVector::ZeroVector));
    TestFalse(TEXT("A master cannot award another master's seal"), State->GrantMasterSeal(TEXT("GM01"), TEXT("WindSeal"), FVector::ZeroVector));
    TestTrue(TEXT("First real master award durably collects its quest seal"), State->GrantMasterSeal(TEXT("GM01"), TEXT("SwordSeal"), FVector(1, 2, 3)));
    TestTrue(TEXT("Quest seal is immediately owned without a health check or pickup"), State->HasSeal(TEXT("SwordSeal")));
    TestFalse(TEXT("Healing supply remains separately uncollected"), State->HasCollectedMasterReward(TEXT("GM01")));
    TestFalse(TEXT("Repeated award cannot duplicate the seal"), State->GrantMasterSeal(TEXT("GM01"), TEXT("SwordSeal"), FVector(999)));
    TestEqual(TEXT("Exactly one seal is listed"), State->GetCollectedSealIds().Num(), 1);
    TestEqual(TEXT("Original healing-drop position is retained"), State->GetProgressionState().MasterRewardLocations.FindRef(TEXT("GM01")), FVector(1, 2, 3));
    FNLProgressionState OldEntrance;
    TestTrue(TEXT("Old entrance snapshot restores"), State->RestoreProgressionState(OldEntrance));
    TestTrue(TEXT("Retry does not remove a collected quest seal"), State->HasSeal(TEXT("SwordSeal")));
    TestTrue(TEXT("Healing reward can still be claimed independently"), State->CollectMasterReward(TEXT("GM01")));
    TestTrue(TEXT("Healing collection does not consume the quest seal"), State->HasSeal(TEXT("SwordSeal")));
    FNLProgressionState LegacyV2;
    LegacyV2.DefeatedMasterIds.Add(TEXT("GM03"));
    LegacyV2.MasterRewardLocations.Add(TEXT("GM03"), FVector(10, 20, 30));
    TestTrue(TEXT("Existing version-two master snapshot restores without a new save schema"), State->RestoreProgressionState(LegacyV2));
    TestTrue(TEXT("A previously recorded v2 first defeat maps to its canonical quest seal"), State->HasSeal(TEXT("AlchemySeal")));
    TestFalse(TEXT("Legacy seal migration still leaves its healing pickup unclaimed"), State->HasCollectedMasterReward(TEXT("GM03")));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLFourSealConfigurationTest,
    "Nilin.LevelEncounter.FourSeals.RejectMismatchedAndUnprovidedQuestIds", NLFourSealTests::Flags)
bool FNLFourSealConfigurationTest::RunTest(const FString& Parameters)
{
    using namespace NLFourSealTests;
    FScopedWorld Fixture;
    if (!TestTrue(TEXT("Isolated configuration world initializes"), Fixture.World && Fixture.Run)) return false;
    auto Add = [&Fixture](const FNLLevelEncounterStage& Stage)
    {
        ANLLevelEncounterDirector* Director = Fixture.World->SpawnActorDeferred<ANLLevelEncounterDirector>(
            ANLLevelEncounterDirector::StaticClass(), FTransform::Identity, nullptr, nullptr,
            ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
        if (Director) { Director->Stages.Add(Stage); Director->FinishSpawning(FTransform::Identity); }
        return Director;
    };
    FNLLevelEncounterStage Wrong = Fixture.Stage(TEXT("Wrong"));
    Wrong.MasterId = TEXT("GM01");
    Wrong.SealId = TEXT("WindSeal");
    AddExpectedError(TEXT("configuration rejected: MasterSealIdentityMismatch"), EAutomationExpectedErrorFlags::Contains, 1);
    ANLLevelEncounterDirector* Mismatched = Add(Wrong);
    if (!TestNotNull(TEXT("Mismatched director remains inspectable"), Mismatched)) return false;
    TestEqual(TEXT("A master cannot be assigned another master's quest item"), Mismatched->GetFailureReason(), FName(TEXT("MasterSealIdentityMismatch")));
    FNLLevelEncounterStage Unprovided = Fixture.Stage(TEXT("BossWithoutMaster"));
    Unprovided.RequiredSealIds.Add(TEXT("SwordSeal"));
    AddExpectedError(TEXT("configuration rejected: MissingSealProvider"), EAutomationExpectedErrorFlags::Contains, 1);
    ANLLevelEncounterDirector* Missing = Add(Unprovided);
    if (!TestNotNull(TEXT("Missing-provider director remains inspectable"), Missing)) return false;
    TestEqual(TEXT("Boss cannot require an item the authored level never provides"), Missing->GetFailureReason(), FName(TEXT("MissingSealProvider")));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLFourSealBossGateTest,
    "Nilin.LevelEncounter.FourSeals.BossNeedsEverySealAndRetryDoesNotConsume", NLFourSealTests::Flags)
bool FNLFourSealBossGateTest::RunTest(const FString& Parameters)
{
    using namespace NLFourSealTests;
    FScopedWorld Fixture;
    if (!TestTrue(TEXT("Isolated world and run initialize"), Fixture.World && Fixture.Run)) return false;
    APawn* Player = Fixture.AddPlayer();
    ANLLevelEncounterDirector* Director = Fixture.AddDirector();
    if (!TestTrue(TEXT("Player and complete stage plan initialize"), Player && Director)) return false;
    TestTrue(TEXT("Seal plan is valid"), Director->GetFailureReason().IsNone());
    TestEqual(TEXT("Boss starts locked"), Director->GetStageStatus(TEXT("Boss")), ENLLevelStageState::Locked);
    TestFalse(TEXT("Walking into the summit cannot bypass missing seals"), Director->TryActivateStage(TEXT("Boss"), Player));
    TestEqual(TEXT("All missing seal identities are exposed to the UI"), Director->GetMissingSealIds(TEXT("Boss")).Num(), 4);
    TestEqual(TEXT("A useful missing-seal reason is exposed"), Director->GetEntryBlockReason(), FName(TEXT("MissingRequiredSeals")));
    Fixture.Run->GrantMasterSeal(TEXT("GM04"), TEXT("WindSeal"), FVector::ZeroVector);
    TestEqual(TEXT("Previously defeated grandmaster is restored as cleared"), Director->GetStageStatus(TEXT("GM04")), ENLLevelStageState::Completed);
    TestFalse(TEXT("Fourth master alone cannot unlock the boss"), Director->TryActivateStage(TEXT("Boss"), Player));
    TestEqual(TEXT("The remaining three seals are named"), Director->GetMissingSealIds(TEXT("Boss")).Num(), 3);
    for (int32 Index = 0; Index < 3; ++Index) Fixture.Run->GrantMasterSeal(Masters[Index], Seals[Index], FVector::ZeroVector);
    TestEqual(TEXT("All four seals make the boss available"), Director->GetStageStatus(TEXT("Boss")), ENLLevelStageState::Available);
    TestTrue(TEXT("Complete quest permits the real stage warning"), Director->TryActivateStage(TEXT("Boss"), Player));
    TestEqual(TEXT("Entry uses the existing encounter state machine"), Director->GetStageStatus(TEXT("Boss")), ENLLevelStageState::Warning);
    TestNull(TEXT("No boss is spawned before warning expiry"), Director->GetActiveEncounter());
    Director->FailActiveStage(TEXT("PlayerRetry"));
    TestTrue(TEXT("Boss retry is allowed"), Director->RetryActiveStage());
    TestEqual(TEXT("Boss retry never consumes the four seals"), Fixture.Run->GetCollectedSealIds().Num(), 4);
    TestEqual(TEXT("Full-health player retained health while earning quest items"), Player->FindComponentByClass<UNLCombatVitalsComponent>()->GetHealth(), 100.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLFourSealLevelResumeTest,
    "Nilin.Progression.FourSeals.LevelRunResumeAndExplicitNewTrial", NLFourSealTests::Flags)
bool FNLFourSealLevelResumeTest::RunTest(const FString& Parameters)
{
    using namespace NLFourSealTests;
    FRunCleanup Cleanup;
    const FName Level = Cleanup.AddLevel();
    UGameInstance* Outer = NewObject<UGameInstance>();
    UNLRunStateSubsystem* First = NewObject<UNLRunStateSubsystem>(Outer);
    if (!TestTrue(TEXT("First level entry creates a durable run identity"), First->ResumeOrBeginLevelRun(Level))) return false;
    const FGuid Original = First->GetRunId();
    Cleanup.Runs.Add(Original);
    TestTrue(TEXT("A master drops its seal"), First->GrantMasterSeal(TEXT("GM02"), TEXT("TalismanSeal"), FVector(100, 200, 50)));
    UNLRunStateSubsystem* Reloaded = NewObject<UNLRunStateSubsystem>(Outer);
    TestTrue(TEXT("Fresh game-instance subsystem resumes the level"), Reloaded->ResumeOrBeginLevelRun(Level));
    TestEqual(TEXT("Run identity survives process-equivalent reload"), Reloaded->GetRunId(), Original);
    TestTrue(TEXT("Automatically collected seal survives reload"), Reloaded->HasSeal(TEXT("TalismanSeal")));
    TestFalse(TEXT("Reload does not auto-consume healing supply"), Reloaded->HasCollectedMasterReward(TEXT("GM02")));
    TestTrue(TEXT("Explicit new trial commits a new identity"), Reloaded->BeginNewLevelRun(Level));
    const FGuid Fresh = Reloaded->GetRunId();
    Cleanup.Runs.Add(Fresh);
    TestTrue(TEXT("New trial has a different run ID"), Fresh != Original);
    TestTrue(TEXT("New trial begins without seals"), Reloaded->GetCollectedSealIds().IsEmpty());
    UNLRunStateSubsystem* NewReload = NewObject<UNLRunStateSubsystem>(Outer);
    TestTrue(TEXT("New trial becomes the next resume target"), NewReload->ResumeOrBeginLevelRun(Level));
    TestEqual(TEXT("Resume follows the explicit new trial"), NewReload->GetRunId(), Fresh);
    UNLRunStateSubsystem* Recovery = NewObject<UNLRunStateSubsystem>(Outer);
    Recovery->BeginRun(Original);
    TestTrue(TEXT("Old run ledger was preserved rather than deleted"), Recovery->HasSeal(TEXT("TalismanSeal")));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLFourSealCorruptProfileTest,
    "Nilin.Progression.FourSeals.CorruptLevelRecordIsPreservedAndRejected", NLFourSealTests::Flags)
bool FNLFourSealCorruptProfileTest::RunTest(const FString& Parameters)
{
    using namespace NLFourSealTests;
    FRunCleanup Cleanup;
    const FName Level = Cleanup.AddLevel();
    UGameInstance* Outer = NewObject<UGameInstance>();
    UNLRunStateSubsystem* State = NewObject<UNLRunStateSubsystem>(Outer);
    if (!TestTrue(TEXT("Test profile initializes"), State->ResumeOrBeginLevelRun(Level))) return false;
    Cleanup.Runs.Add(State->GetRunId());
    State->GrantMasterSeal(TEXT("GM01"), TEXT("SwordSeal"), FVector::ZeroVector);
    const FString Path = MarkerPath(Level);
    TArray<uint8> Bytes;
    if (!TestTrue(TEXT("Marker has fixed bounded size"), FFileHelper::LoadFileToArray(Bytes, *Path) && Bytes.Num() == 48)) return false;
    Bytes[0] ^= 1;
    if (!TestTrue(TEXT("Test corruption is written"), FFileHelper::SaveArrayToFile(Bytes, *Path))) return false;
    TestFalse(TEXT("Damaged resume record is rejected"), State->ResumeOrBeginLevelRun(Level));
    TestEqual(TEXT("Failure identifies the damaged profile"), State->GetLastFailureReason(), FName(TEXT("LevelRunRecordCorrupt")));
    TestFalse(TEXT("Failed level load cannot expose a stale run's seals"), State->HasSeal(TEXT("SwordSeal")));
    TestFalse(TEXT("New quest drops are blocked until explicit recovery"), State->GrantMasterSeal(TEXT("GM02"), TEXT("TalismanSeal"), FVector::ZeroVector));
    TArray<uint8> After;
    TestTrue(TEXT("Damaged data remains intact for recovery"), FFileHelper::LoadFileToArray(After, *Path) && After == Bytes);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLFourSealReentrantGrantTest,
    "Nilin.Progression.FourSeals.GrantCallbackNewRunCannotReplaySealFeedback", NLFourSealTests::Flags)
bool FNLFourSealReentrantGrantTest::RunTest(const FString& Parameters)
{
    using namespace NLFourSealTests;
    FScopedWorld F;
    if (!TestNotNull(TEXT("Isolated run subsystem"), F.Run)) return false;
    const FGuid PreviousRun = F.Run->GetRunId();
    const FGuid NextRun = F.Cleanup.AddRun();
    const FVector OriginalDrop(123, 456, 78);
    UNLRunCallbackTestListener* Listener = NewObject<UNLRunCallbackTestListener>(F.Instance);
    bool bObservedCommittedSeal = false;
    Listener->Callback = [&]()
    {
        bObservedCommittedSeal = F.Run->HasSeal(TEXT("SwordSeal"));
        F.Run->OnRunStateChanged.RemoveDynamic(Listener, &UNLRunCallbackTestListener::HandleRunChanged);
        F.Run->BeginRun(NextRun);
    };
    F.Run->OnRunStateChanged.AddDynamic(Listener, &UNLRunCallbackTestListener::HandleRunChanged);
    TestTrue(TEXT("The first seal really commits before the listener starts another run"),
        F.Run->GrantMasterSeal(TEXT("GM01"), TEXT("SwordSeal"), OriginalDrop));
    F.Run->OnRunStateChanged.RemoveDynamic(Listener, &UNLRunCallbackTestListener::HandleRunChanged);
    TestTrue(TEXT("Callback saw the durably committed original seal"), bObservedCommittedSeal);
    TestTrue(TEXT("Callback's new run identity survives the original grant"), F.Run->GetRunId() == NextRun);
    TestEqual(TEXT("The new run has no previous-run quest items"), F.Run->GetCollectedSealIds().Num(), 0);
    TestTrue(TEXT("The new run receives no stale acquisition toast"), F.Run->GetLastAcquiredSealId().IsNone());
    TestEqual(TEXT("The new run receives no stale toast timestamp"), F.Run->GetLastSealAcquiredTimeSeconds(), -1.0);
    TestTrue(TEXT("The successful old-run commit does not fail the new run"), F.Run->GetLastFailureReason().IsNone());

    F.Run->BeginRun(PreviousRun);
    TestTrue(TEXT("Reloading the original ledger retains its genuinely awarded seal"), F.Run->HasSeal(TEXT("SwordSeal")));
    TestEqual(TEXT("The original durable drop location remains unchanged"),
        F.Run->GetProgressionState().MasterRewardLocations.FindRef(TEXT("GM01")), OriginalDrop);
    TestTrue(TEXT("Loading the old ledger itself does not replay acquisition feedback"), F.Run->GetLastAcquiredSealId().IsNone());
    TestFalse(TEXT("A repeated original-run grant remains idempotent"),
        F.Run->GrantMasterSeal(TEXT("GM01"), TEXT("SwordSeal"), FVector(999)));
    TestTrue(TEXT("A duplicate grant does not replay acquisition feedback"), F.Run->GetLastAcquiredSealId().IsNone());
    TestEqual(TEXT("A duplicate grant does not replay its timestamp"), F.Run->GetLastSealAcquiredTimeSeconds(), -1.0);

    F.Run->BeginRun(NextRun);
    TestTrue(TEXT("A real grant in the new run still works normally"),
        F.Run->GrantMasterSeal(TEXT("GM02"), TEXT("TalismanSeal"), FVector(321, 654, 87)));
    TestEqual(TEXT("A real new-run grant exposes its own acquisition feedback"), F.Run->GetLastAcquiredSealId(), FName(TEXT("TalismanSeal")));
    TestEqual(TEXT("Only the genuinely awarded new-run seal is owned"), F.Run->GetCollectedSealIds().Num(), 1);
    return true;
}

#endif
