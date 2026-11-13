#if WITH_DEV_AUTOMATION_TESTS

#include "AI/NLEnemyBrainComponent.h"
#include "AI/NLEnemyCharacter.h"
#include "AI/NLAttackDirectorSubsystem.h"
#include "Animation/AnimSequenceBase.h"
#include "Combat/NLAttackDefinition.h"
#include "Combat/NLBladeComponent.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatResolverSubsystem.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "CoreGlobals.h"
#include "Engine/Engine.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/WorldSettings.h"
#include "Misc/AutomationTest.h"
#include "PhysicsEngine/PhysicsAsset.h"

struct FNLEnemyOptimizationTestAccess
{
    static void Prepare(ANLEnemyCharacter* Enemy, AActor* Target)
    {
        UNLEnemyBrainComponent* Brain = Enemy->GetEnemyBrain();
        Enemy->bCombatEnabled = true;
        Enemy->bLabPaused = false;
        Brain->TargetActor = Target;
        Brain->AttackDirector = Enemy->GetWorld()->GetSubsystem<UNLAttackDirectorSubsystem>();
        Brain->bActiveRegistered = Brain->AttackDirector->TryRegisterActiveFighter(Enemy);
        Brain->State = ENLEnemyState::Approach;
        Brain->StateElapsed = 0;
        Brain->RetryElapsed = 1;
    }
    static bool Navigation(UNLEnemyBrainComponent* Brain, float Delta) { return Brain->WaitForNavigationReady(Delta); }
    static void FailPath(UNLEnemyBrainComponent* Brain)
    {
        Brain->bNavigationRetryPending = false;
        Brain->HandlePathFailure();
    }
    static void Approach(UNLEnemyBrainComponent* Brain) { Brain->UpdateApproach(.1f); }
    static void Wait(UNLEnemyBrainComponent* Brain) { Brain->RetryElapsed = 1.0f; Brain->UpdateWaitForSlot(.1f); }
    static void TickBrain(UNLEnemyBrainComponent* Brain, float Delta) { Brain->TickComponent(Delta, LEVELTICK_All, nullptr); }
    static float Telegraph(UNLEnemyBrainComponent* Brain) { return Brain->GetTelegraphDuration(); }
    static void Walk(ANLEnemyCharacter* Enemy, float Delta) { Enemy->UpdateWalkPresentation(Delta); }
    static float WalkRate(ANLEnemyCharacter* Enemy) { return Enemy->SmoothedWalkRate; }
};

namespace NLEnemyOptimizationTests
{
    constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
    struct FWorld
    {
        UWorld* World = nullptr;
        AActor* Player = nullptr;
        ANLEnemyCharacter* Enemy = nullptr;
        UNLAttackDefinition* Attack = nullptr;
        uint64 Frame = GFrameCounter;
        FWorld(bool bPhysics = false, bool bNativeRagdoll = false)
        {
            if (!GEngine) return;
            const UWorld::InitializationValues Values = UWorld::InitializationValues().AllowAudioPlayback(false)
                .RequiresHitProxies(false).CreatePhysicsScene(true).ShouldSimulatePhysics(bPhysics)
                .EnableTraceCollision(true).CreateNavigation(false).CreateAISystem(false);
            World = UWorld::CreateWorld(EWorldType::Game, false,
                FName(*FString::Printf(TEXT("NilinEnemyOpt_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Digits))),
                nullptr, true, ERHIFeatureLevel::Num, &Values);
            if (!World) return;
            GEngine->CreateNewWorldContext(World->WorldType).SetCurrentWorld(World);
            World->InitializeActorsForPlay(FURL());
            World->BeginPlay();
            World->GetWorldSettings()->NotifyBeginPlay();
            AActor* Floor = World->SpawnActor<AActor>();
            UBoxComponent* Box = NewObject<UBoxComponent>(Floor);
            Floor->AddInstanceComponent(Box); Floor->SetRootComponent(Box);
            Box->InitBoxExtent(FVector(2000, 2000, 20));
            Box->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
            Box->SetCollisionObjectType(ECC_WorldStatic); Box->SetCollisionResponseToAllChannels(ECR_Block);
            Box->RegisterComponent(); Box->SetWorldLocation(FVector(0, 0, -20));
            Player = World->SpawnActor<AActor>();
            USceneComponent* Root = NewObject<USceneComponent>(Player);
            Player->SetRootComponent(Root); Player->AddInstanceComponent(Root); Root->RegisterComponent();
            Player->SetActorLocation(FVector(5000, 0, 88));
            UNLCombatIdentityComponent* Identity = NewObject<UNLCombatIdentityComponent>(Player);
            Identity->Faction = ENLCombatFaction::Player; Player->AddInstanceComponent(Identity); Identity->RegisterComponent();
            UNLCombatVitalsComponent* Vitals = NewObject<UNLCombatVitalsComponent>(Player);
            Player->AddInstanceComponent(Vitals); Vitals->RegisterComponent(); Vitals->ResetVitals();
            Attack = NewObject<UNLAttackDefinition>(World); Attack->StableId = TEXT("Automation.EnemyOpt.Attack"); Attack->Damage = 100;
            const FTransform Spawn(FRotator::ZeroRotator, FVector(0, 0, 88));
            Enemy = World->SpawnActorDeferred<ANLEnemyCharacter>(ANLEnemyCharacter::StaticClass(), Spawn,
                nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
            if (!Enemy) return;
            Enemy->AutoPossessAI = EAutoPossessAI::Disabled;
            if (bNativeRagdoll)
            {
                Enemy->EnemySkeletalMesh = LoadObject<USkeletalMesh>(nullptr,
                    TEXT("/Game/ReversedScale/Characters/WuxiaMale/NativeRigV07/SK_WuxiaMale_Native_v07.SK_WuxiaMale_Native_v07"));
                Enemy->RagdollPhysicsAsset = LoadObject<UPhysicsAsset>(nullptr,
                    TEXT("/Game/ReversedScale/Characters/Physics1111/PHYS_SK_WuxiaMale_Native_v07_Fitted.PHYS_SK_WuxiaMale_Native_v07_Fitted"));
                Enemy->IdleAnimation = LoadObject<UAnimationAsset>(nullptr,
                    TEXT("/Game/ReversedScale/Characters/WuxiaMale/NativeRigV07/A_Wuxia_Idle_Native_v07.A_Wuxia_Idle_Native_v07"));
                Enemy->GetMesh()->SetRelativeRotation(FRotator::ZeroRotator);
                Enemy->SwordAttachBone = TEXT("RightHand");
            }
            Enemy->EnemyAttackDefinition = Attack;
            Enemy->FinishSpawning(Spawn);
            Enemy->GetEnemyBrain()->SetComponentTickEnabled(false);
            FNLEnemyOptimizationTestAccess::Prepare(Enemy, Player);
        }
        ~FWorld()
        {
            if (World) { World->EndPlay(EEndPlayReason::Quit); GEngine->DestroyWorldContext(World); World->DestroyWorld(false); }
            GFrameCounter = Frame;
        }
        void Step(float Delta = 1.0f / 60.0f) { ++GFrameCounter; World->Tick(LEVELTICK_All, Delta); }
        FNLCombatResult Strike()
        {
            FNLCombatContact C;
            C.AttackInstanceId = FGuid::NewGuid(); C.AttackDefinitionId = Attack->StableId;
            C.SourceRuntimeId = Player->FindComponentByClass<UNLCombatIdentityComponent>()->EnsureRuntimeId();
            C.TargetRuntimeId = Enemy->CombatIdentity->EnsureRuntimeId();
            C.HitPosition = Enemy->GetActorLocation();
            return World->GetSubsystem<UNLCombatResolverSubsystem>()->ResolveContact(Player, Enemy, C, Attack);
        }
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLEnemyNavigationSurvivalTest, "Nilin.EnemyOptimization.NavigationRecoveryKeepsCombatAndDefeat", NLEnemyOptimizationTests::Flags)
bool FNLEnemyNavigationSurvivalTest::RunTest(const FString& Parameters)
{
    NLEnemyOptimizationTests::FWorld F;
    if (!F.Enemy || !F.Player) return false;
    UNLEnemyBrainComponent* Brain = F.Enemy->GetEnemyBrain();
    TestFalse(TEXT("No nav tile waits instead of pretending to path"), FNLEnemyOptimizationTestAccess::Navigation(Brain, 11.0f));
    for (int32 I = 0; I < 8; ++I) FNLEnemyOptimizationTestAccess::FailPath(Brain);
    TestTrue(TEXT("Repeated navigation failures never despawn a living enemy"), Brain->GetState() != ENLEnemyState::Despawn);
    TestFalse(TEXT("Enemy remains visible"), F.Enemy->IsHidden());
    F.Player->SetActorLocation(FVector(100, 0, 88));
    TestTrue(TEXT("Player approaching admits stationary combat without navigation"), FNLEnemyOptimizationTestAccess::Navigation(Brain, .1f));
    FNLEnemyOptimizationTestAccess::TickBrain(Brain, .4f);
    FNLEnemyOptimizationTestAccess::TickBrain(Brain, .4f);
    TestEqual(TEXT("Unnavigable melee enemy can still telegraph a real reserved attack"), Brain->GetState(), ENLEnemyState::Telegraph);
    const FNLCombatResult Result = F.Strike();
    TestTrue(TEXT("The normal combat resolver can defeat this enemy"), Result.bTargetDefeated && Result.AppliedDamage > 0);
    TestEqual(TEXT("Death uses the normal brain terminal state"), Brain->GetState(), ENLEnemyState::Dead);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLEnemyRangedEngagementTest, "Nilin.EnemyOptimization.RangedAttacksBeforeMeleeDistance", NLEnemyOptimizationTests::Flags)
bool FNLEnemyRangedEngagementTest::RunTest(const FString& Parameters)
{
    NLEnemyOptimizationTests::FWorld F;
    if (!F.Enemy) return false;
    UNLEnemyBrainComponent* Brain = F.Enemy->GetEnemyBrain();
    Brain->Role = ENLEnemyRole::TalismanCaster; Brain->RangedAttackDefinition = F.Attack;
    Brain->bHoldRangedPosition = true;
    F.Player->SetActorLocation(FVector(1000, 0, 88));
    TestTrue(TEXT("A fixed caster with clear sight attacks without a nav tile"), FNLEnemyOptimizationTestAccess::Navigation(Brain, .1f));
    FNLEnemyOptimizationTestAccess::Approach(Brain); FNLEnemyOptimizationTestAccess::Wait(Brain);
    TestEqual(TEXT("Caster reserves its warning ten metres away"), Brain->GetState(), ENLEnemyState::Telegraph);
    TestTrue(TEXT("Warning is faster but retains a readable minimum"), FNLEnemyOptimizationTestAccess::Telegraph(Brain) >= .55f && FNLEnemyOptimizationTestAccess::Telegraph(Brain) < 1.0f);
    Brain->Role = ENLEnemyRole::FormationBreaker;
    TestTrue(TEXT("Ritual breaker keeps its deliberate warning"), FNLEnemyOptimizationTestAccess::Telegraph(Brain) >= 1.5f);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLEnemyRagdollResetTest, "Nilin.EnemyOptimization.RagdollFallsOnFloorAndResets", NLEnemyOptimizationTests::Flags)
bool FNLEnemyRagdollResetTest::RunTest(const FString& Parameters)
{
    NLEnemyOptimizationTests::FWorld F(true, true);
    if (!F.Enemy || !TestNotNull(TEXT("Authored native-rig physics asset must be installed"), F.Enemy->RagdollPhysicsAsset.Get())) return false;
    F.Player->SetActorLocation(FVector(100, 0, 88));
    F.Enemy->GetMesh()->TickAnimation(0, false); F.Enemy->GetMesh()->RefreshBoneTransforms();
    const FVector Initial = F.Enemy->GetMesh()->GetBoneLocation(TEXT("Hips"));
    TestTrue(TEXT("Normal combat damage defeats enemy"), F.Strike().bTargetDefeated);
    for (int32 I = 0; I < 180; ++I) F.Step();
    const FVector Fallen = F.Enemy->GetMesh()->GetBoneLocation(TEXT("Hips"));
    TestTrue(TEXT("The real skeletal body simulates"), F.Enemy->IsRagdollActive() && F.Enemy->GetMesh()->IsSimulatingPhysics());
    TestTrue(TEXT("Pelvis physically falls from the standing pose"), Fallen.Z < Initial.Z - 20.0);
    TestTrue(TEXT("The world floor catches the ragdoll"), Fallen.Z > -25.0 && FVector::Dist2D(Initial, Fallen) < 1000.0);
    TestEqual(TEXT("Corpse never blocks player locomotion"), F.Enemy->GetMesh()->GetCollisionResponseToChannel(ECC_Pawn), ECR_Ignore);
    F.Enemy->ResetForEncounter();
    for (int32 I = 0; I < 5; ++I) F.Step();
    TestFalse(TEXT("Reset disables all ragdoll simulation"), F.Enemy->IsRagdollActive() || F.Enemy->GetMesh()->IsSimulatingPhysics());
    TestFalse(TEXT("Reset restores living resources"), F.Enemy->Vitals->IsDead());
    TestTrue(TEXT("Reset restores the capsule and attachment"), F.Enemy->GetCapsuleComponent()->GetCollisionEnabled() != ECollisionEnabled::NoCollision
        && F.Enemy->GetMesh()->GetAttachParent() == F.Enemy->GetCapsuleComponent());
    TestTrue(TEXT("Reset returns pelvis above the floor"), F.Enemy->GetMesh()->GetBoneLocation(TEXT("Hips")).Z > 50.0);
    return !HasAnyErrors();
}

#endif
