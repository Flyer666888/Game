#if WITH_DEV_AUTOMATION_TESTS

#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Components/SphereComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/WorldSettings.h"
#include "HAL/PlatformFileManager.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/AutomationTest.h"
#include "Misc/Paths.h"
#include "Pickup/NLHealingPickup.h"
#include "Progression/NLMasterRewardSubsystem.h"
#include "Progression/NLRunStateSubsystem.h"
#include "Save/NLCheckpointSaveGame.h"
#include "Save/NLCheckpointService.h"
#include "Serialization/MemoryReader.h"
#include "Serialization/MemoryWriter.h"

namespace NLMasterRewardTests
{
    constexpr EAutomationTestFlags TestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

    void DeleteTestLedger(FGuid Id)
    {
        const FString Path = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(),
            TEXT("SaveGames/NilinMasterRewards"), Id.ToString(EGuidFormats::Digits) + TEXT(".nlmr")));
        IPlatformFile& Files = FPlatformFileManager::Get().GetPlatformFile();
        Files.DeleteFile(*Path);
        Files.DeleteFile(*(Path + TEXT(".tmp")));
    }

    struct FTestRun
    {
        FGuid Id = FGuid::NewGuid();
        ~FTestRun() { DeleteTestLedger(Id); }
    };

    struct FScopedRewardWorld
    {
        UWorld* World = nullptr;
        UGameInstance* GameInstance = nullptr;
        UNLRunStateSubsystem* State = nullptr;
        UNLMasterRewardSubsystem* Rewards = nullptr;
        FTestRun Run;

        FScopedRewardWorld()
        {
            if (!GEngine) return;
            const UWorld::InitializationValues Values = UWorld::InitializationValues()
                .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true)
                .ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateNavigation(false).CreateAISystem(false);
            World = UWorld::CreateWorld(EWorldType::Game, false,
                FName(*FString::Printf(TEXT("NilinMasterReward_%s"), *Run.Id.ToString(EGuidFormats::Digits))),
                nullptr, true, ERHIFeatureLevel::Num, &Values);
            if (!World) return;
            GameInstance = NewObject<UGameInstance>(GEngine);
            World->SetGameInstance(GameInstance);
            FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
            Context.SetCurrentWorld(World);
            Context.OwningGameInstance = GameInstance;
            GameInstance->Init();
            State = GameInstance->GetSubsystem<UNLRunStateSubsystem>();
            World->InitializeActorsForPlay(FURL());
            World->BeginPlay();
            if (AWorldSettings* Settings = World->GetWorldSettings()) Settings->NotifyBeginPlay();
            Rewards = World->GetSubsystem<UNLMasterRewardSubsystem>();
            if (State) State->BeginRun(Run.Id);
        }

        ~FScopedRewardWorld()
        {
            if (World)
            {
                World->EndPlay(EEndPlayReason::Quit);
                if (GEngine) GEngine->DestroyWorldContext(World);
                World->DestroyWorld(false);
            }
            if (GameInstance) GameInstance->Shutdown();
        }

        AActor* AddBody(ENLCombatFaction Faction, float Health)
        {
            FActorSpawnParameters Parameters;
            Parameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
            AActor* Actor = World->SpawnActor<AActor>(FVector(1000.0, 0.0, 100.0), FRotator::ZeroRotator, Parameters);
            if (!Actor) return nullptr;
            USphereComponent* Collision = NewObject<USphereComponent>(Actor);
            Collision->InitSphereRadius(30.0f);
            Collision->SetCollisionObjectType(ECC_Pawn);
            Collision->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
            Collision->SetCollisionResponseToAllChannels(ECR_Overlap);
            Collision->SetGenerateOverlapEvents(true);
            Actor->SetRootComponent(Collision);
            Actor->AddInstanceComponent(Collision);
            Collision->RegisterComponent();
            Actor->SetActorLocation(FVector(1000.0, 0.0, 100.0));
            UNLCombatIdentityComponent* Identity = NewObject<UNLCombatIdentityComponent>(Actor);
            Identity->Faction = Faction;
            Actor->AddInstanceComponent(Identity);
            Identity->RegisterComponent();
            UNLCombatVitalsComponent* Vitals = NewObject<UNLCombatVitalsComponent>(Actor);
            Actor->AddInstanceComponent(Vitals);
            Vitals->RegisterComponent();
            Vitals->MaxHealth = 100.0f;
            Vitals->ResetVitals();
            Vitals->Health = Health;
            return Actor;
        }
    };
}

using namespace NLMasterRewardTests;

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLMasterRewardMonotonicTest,
    "Nilin.Progression.MasterRewards.PersistentFirstDefeatAndRollback", NLMasterRewardTests::TestFlags)

bool FNLMasterRewardMonotonicTest::RunTest(const FString& Parameters)
{
    FTestRun Run;
    FTestRun NewRun;
    UGameInstance* Outer = NewObject<UGameInstance>();
    UNLRunStateSubsystem* State = NewObject<UNLRunStateSubsystem>(Outer);
    State->BeginRun(Run.Id);
    const FNLProgressionState BeforeDefeat = State->GetProgressionState();
    TestTrue(TEXT("First master defeat is durably recorded"), State->RecordMasterDefeat(TEXT("GM01"), FVector(100, 200, 300)));
    TestFalse(TEXT("Duplicate defeat cannot move/regrant the drop"), State->RecordMasterDefeat(TEXT("GM01"), FVector(999)));
    TestEqual(TEXT("Original drop location is retained"), State->GetProgressionState().MasterRewardLocations.FindRef(TEXT("GM01")), FVector(100, 200, 300));
    TestTrue(TEXT("First claim succeeds"), State->CollectMasterReward(TEXT("GM01")));
    TestFalse(TEXT("Duplicate claim is rejected"), State->CollectMasterReward(TEXT("GM01")));
    TestTrue(TEXT("Old entrance progression can restore"), State->RestoreProgressionState(BeforeDefeat));
    TestTrue(TEXT("Checkpoint rollback cannot erase defeat"), State->HasDefeatedMaster(TEXT("GM01")));
    TestTrue(TEXT("Checkpoint rollback cannot erase collection"), State->HasCollectedMasterReward(TEXT("GM01")));
    TestEqual(TEXT("Master drops do not change generic enemy ledger"), State->GetDefeatEventCount(), 0);

    UNLRunStateSubsystem* Reloaded = NewObject<UNLRunStateSubsystem>(Outer);
    Reloaded->BeginRun(Run.Id);
    TestTrue(TEXT("Fresh subsystem loads persisted collection without any checkpoint"), Reloaded->HasCollectedMasterReward(TEXT("GM01")));
    TestTrue(TEXT("Old disk checkpoint cannot erase fresh session's durable claim"), Reloaded->RestoreProgressionState(BeforeDefeat));
    TestFalse(TEXT("Old snapshot cannot make first defeat repeatable"), Reloaded->RecordMasterDefeat(TEXT("GM01"), FVector::ZeroVector));
    Reloaded->BeginRun(NewRun.Id);
    TestFalse(TEXT("New run starts with an empty master ledger"), Reloaded->HasDefeatedMaster(TEXT("GM01")));
    TestTrue(TEXT("New run can earn the same master reward"), Reloaded->RecordMasterDefeat(TEXT("GM01"), FVector::ZeroVector));
    TestFalse(TEXT("Non-master IDs cannot earn first-kill supplies"), Reloaded->RecordMasterDefeat(TEXT("GM05"), FVector::ZeroVector));
    FNLProgressionState Invalid;
    Invalid.CollectedMasterRewards.Add(TEXT("GM04"));
    TestFalse(TEXT("A claim without a corresponding defeat is invalid"), Reloaded->RestoreProgressionState(Invalid));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLMasterRewardPickupTest,
    "Nilin.Progression.MasterRewards.PickupPlayerHealthAndPendingReload", NLMasterRewardTests::TestFlags)

bool FNLMasterRewardPickupTest::RunTest(const FString& Parameters)
{
    FScopedRewardWorld Fixture;
    if (!TestTrue(TEXT("Game-instance and world reward services initialize"), Fixture.World && Fixture.State && Fixture.Rewards)) return false;
    ANLHealingPickup* Pickup = Fixture.Rewards->SpawnFirstDefeatReward(TEXT("GM01"), FVector(0, 0, 100));
    if (!TestNotNull(TEXT("First defeat creates healing spirit"), Pickup)) return false;
    TestEqual(TEXT("Repeated defeat returns the same pending actor"),
        Fixture.Rewards->SpawnFirstDefeatReward(TEXT("GM01"), FVector(500, 500, 100)), Pickup);
    TestEqual(TEXT("Default supply restores up to 25 HP"), Pickup->GetHealthAmount(), 25.0f);
    Pickup->Destroy();
    Fixture.Rewards->RestorePendingRewards();
    Pickup = Fixture.Rewards->GetPendingReward(TEXT("GM01"));
    if (!TestNotNull(TEXT("Uncollected pickup is rebuilt after actor loss/reload"), Pickup)) return false;
    TestEqual(TEXT("Pending reward uses original saved position"), Pickup->GetActorLocation(), FVector(0, 0, 100));

    AActor* Enemy = Fixture.AddBody(ENLCombatFaction::Enemy, 10.0f);
    AActor* Player = Fixture.AddBody(ENLCombatFaction::Player, 100.0f);
    if (!TestTrue(TEXT("Test combat actors initialize"), Enemy && Player)) return false;
    UNLCombatVitalsComponent* Vitals = Player->FindComponentByClass<UNLCombatVitalsComponent>();
    TestFalse(TEXT("An enemy cannot consume a player supply"), Pickup->TryCollect(Enemy));
    TestFalse(TEXT("Full health leaves supply intact"), Pickup->TryCollect(Player));
    TestFalse(TEXT("Full health does not record collection"), Fixture.State->HasCollectedMasterReward(TEXT("GM01")));
    Vitals->Health = 0.0f;
    TestFalse(TEXT("Dead players cannot use supplies to revive"), Pickup->TryCollect(Player));
    TestFalse(TEXT("Death leaves supply available"), Fixture.State->HasCollectedMasterReward(TEXT("GM01")));
    Vitals->Health = 90.0f;
    TestTrue(TEXT("Living injured player receives supply"), Pickup->TryCollect(Player));
    TestEqual(TEXT("Healing clamps to maximum health"), Vitals->GetHealth(), 100.0f);
    TestTrue(TEXT("Successful pickup records durable claim"), Fixture.State->HasCollectedMasterReward(TEXT("GM01")));
    TestFalse(TEXT("Repeated overlap cannot heal twice"), Pickup->TryCollect(Player));
    Fixture.Rewards->RestorePendingRewards();
    TestNull(TEXT("Collected supply cannot be restored"), Fixture.Rewards->GetPendingReward(TEXT("GM01")));
    TestNull(TEXT("Repeated master defeat cannot respawn collected supply"),
        Fixture.Rewards->SpawnFirstDefeatReward(TEXT("GM01"), FVector::ZeroVector));

    AActor* WalkingPlayer = Fixture.AddBody(ENLCombatFaction::Player, 50.0f);
    if (!TestNotNull(TEXT("A second injured player initializes"), WalkingPlayer)) return false;
    Pickup = Fixture.Rewards->SpawnFirstDefeatReward(TEXT("GM02"), FVector(0, 1000, 100));
    if (!TestNotNull(TEXT("Second master's reward initializes"), Pickup)) return false;
    WalkingPlayer->SetActorLocation(FVector(0, 1000, 100));
    Fixture.World->Tick(LEVELTICK_All, 0.02f);
    TestEqual(TEXT("Real pawn overlap collects the second supply"),
        WalkingPlayer->FindComponentByClass<UNLCombatVitalsComponent>()->GetHealth(), 75.0f);
    TestTrue(TEXT("Overlap collection is logged exactly once"), Fixture.State->HasCollectedMasterReward(TEXT("GM02")));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLMasterRewardCheckpointRoundtripTest,
    "Nilin.Progression.MasterRewards.CheckpointV2Roundtrip", NLMasterRewardTests::TestFlags)

bool FNLMasterRewardCheckpointRoundtripTest::RunTest(const FString& Parameters)
{
    UNLCheckpointSaveGame* Save = NewObject<UNLCheckpointSaveGame>();
    FNLCheckpointSnapshot& Snapshot = Save->Snapshot;
    Snapshot.RunId = FGuid::NewGuid();
    Snapshot.ContentRevision = TEXT("Test.MasterRewards.1");
    Snapshot.LevelId = TEXT("Test.Level");
    Snapshot.NodeId = TEXT("Test.Node");
    Snapshot.EncounterId = TEXT("Test.Encounter");
    Snapshot.CheckpointId = TEXT("Test.Checkpoint");
    Snapshot.OrderedWaveIds.Add(TEXT("Test.Wave"));
    Snapshot.ProgressionState.DefeatedMasterIds = {TEXT("GM01"), TEXT("GM02")};
    Snapshot.ProgressionState.CollectedMasterRewards.Add(TEXT("GM01"));
    Snapshot.ProgressionState.MasterRewardLocations.Add(TEXT("GM01"), FVector(100, 200, 300));
    Snapshot.ProgressionState.MasterRewardLocations.Add(TEXT("GM02"), FVector(400, 500, 600));
    FName Failure;
    TestTrue(TEXT("Snapshot validates with distinct pending and collected masters"), UNLCheckpointService::ValidateSnapshot(Snapshot, Failure));
    TArray<uint8> Bytes;
    if (!TestTrue(TEXT("Custom checkpoint serializer writes v2"), UGameplayStatics::SaveGameToMemory(Save, Bytes) && Save->WasSerializationValid())) return false;
    UNLCheckpointSaveGame* Loaded = Cast<UNLCheckpointSaveGame>(UGameplayStatics::LoadGameFromMemory(Bytes));
    if (!TestNotNull(TEXT("Dedicated checkpoint class reloads"), Loaded)) return false;
    TestTrue(TEXT("Bounded serializer accepts v2"), Loaded->WasSerializationValid());
    TestEqual(TEXT("First-defeat IDs survive manual serialization"), Loaded->Snapshot.ProgressionState.DefeatedMasterIds.Num(), 2);
    TestEqual(TEXT("Collection IDs survive manual serialization"), Loaded->Snapshot.ProgressionState.CollectedMasterRewards.Num(), 1);
    TestEqual(TEXT("Pending drop position survives manual serialization"),
        Loaded->Snapshot.ProgressionState.MasterRewardLocations.FindRef(TEXT("GM02")), FVector(400, 500, 600));

    // A v1 body has the same bounded fields and omits the two master-array counts.
    // Exercise the actual legacy reader rather than merely accepting a v1 input struct.
    UNLCheckpointSaveGame* LegacySource = NewObject<UNLCheckpointSaveGame>();
    LegacySource->Snapshot = Snapshot;
    LegacySource->Snapshot.ProgressionState.DefeatedMasterIds.Reset();
    LegacySource->Snapshot.ProgressionState.CollectedMasterRewards.Reset();
    LegacySource->Snapshot.ProgressionState.MasterRewardLocations.Reset();
    TArray<uint8> LegacyBody;
    {
        FMemoryWriter Writer(LegacyBody, true);
        LegacySource->Serialize(Writer);
    }
    if (!TestTrue(TEXT("Empty v2 body has room for both appended array counts"), LegacyBody.Num() > 16)) return false;
    LegacyBody.SetNum(LegacyBody.Num() - 2 * sizeof(int32));
    const int32 LegacyVersion = 1;
    FMemory::Memcpy(LegacyBody.GetData() + sizeof(uint32), &LegacyVersion, sizeof(int32));
    UNLCheckpointSaveGame* LegacyLoaded = NewObject<UNLCheckpointSaveGame>();
    FMemoryReader LegacyReader(LegacyBody, true);
    LegacyLoaded->Serialize(LegacyReader);
    TestTrue(TEXT("Delivered version-one checkpoint body remains readable"), LegacyLoaded->WasSerializationValid());
    TestEqual(TEXT("Legacy body carries version one"), LegacyLoaded->Snapshot.SaveVersion, 1);
    TestTrue(TEXT("Legacy checkpoint initializes an empty master ledger"), LegacyLoaded->Snapshot.ProgressionState.DefeatedMasterIds.IsEmpty());
    return true;
}

#endif
