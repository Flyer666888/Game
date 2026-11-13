#if WITH_DEV_AUTOMATION_TESTS

#include "AI/NLEnemyCharacter.h"
#include "AI/NLEnemyBrainComponent.h"
#include "Animation/AnimSequenceBase.h"
#include "Combat/NLBladeComponent.h"
#include "Components/BoxComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "CoreGlobals.h"
#include "Curves/CurveVector.h"
#include "Engine/Engine.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/WorldSettings.h"
#include "Misc/AutomationTest.h"

/** The fixture supplies animation clock samples; production playback, root travel,
 *  collision sweeps and lifecycle cancellation are used without navigation. */
struct FNLAttackRootMotionTestAccess
{
    static void Attack(ANLEnemyCharacter* Enemy)
    {
        Enemy->bCombatEnabled = true;
        Enemy->PlayOneShot(Enemy->AttackAnimation,false,true);
    }
    static void Sample(ANLEnemyCharacter* Enemy,float Time)
    {
        Enemy->GetMesh()->SetPosition(Time,false);
        Enemy->UpdateAttackRootMotion();
    }
    static void Cancel(ANLEnemyCharacter* Enemy)
    {
        Enemy->HandleAttackCancelled(Enemy,nullptr,TEXT("Test.Interrupt"));
    }
    static void React(ANLEnemyCharacter* Enemy)
    {
        Enemy->PlayOneShot(Enemy->AttackAnimation,false,false);
    }
    static void Die(ANLEnemyCharacter* Enemy) { Enemy->HandleDied(); }
};

namespace NLEnemyRootMotionTests
{
    constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
    struct FWorld
    {
        UWorld* World = nullptr;
        ANLEnemyCharacter* Enemy = nullptr;
        uint64 SavedFrameCounter = GFrameCounter;
        FWorld()
        {
            if (!GEngine) return;
            const UWorld::InitializationValues Values = UWorld::InitializationValues()
                .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true)
                .ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateNavigation(false).CreateAISystem(false);
            World = UWorld::CreateWorld(EWorldType::Game,false,
                FName(*FString::Printf(TEXT("NilinAttackTravel_%s"),*FGuid::NewGuid().ToString(EGuidFormats::Digits))),
                nullptr,true,ERHIFeatureLevel::Num,&Values);
            if (!World) return;
            GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            World->InitializeActorsForPlay(FURL());
            World->BeginPlay();
            World->GetWorldSettings()->NotifyBeginPlay();
            USkeletalMesh* Mesh = LoadObject<USkeletalMesh>(nullptr,
                TEXT("/Game/ReversedScale/Characters/WuxiaMale/NativeRigV07/SK_WuxiaMale_Native_v07.SK_WuxiaMale_Native_v07"));
            UAnimSequenceBase* Clip = LoadObject<UAnimSequenceBase>(nullptr,
                TEXT("/Game/ReversedScale/Characters/WuxiaMale/NativeRigV07/A_Wuxia_Attack_Native_v07.A_Wuxia_Attack_Native_v07"));
            if (!Mesh || !Clip || Clip->GetPlayLength() < 1.5f) return;
            const FTransform Spawn(FRotator::ZeroRotator,FVector(0,0,88));
            Enemy = World->SpawnActorDeferred<ANLEnemyCharacter>(ANLEnemyCharacter::StaticClass(),Spawn,
                nullptr,nullptr,ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
            if (!Enemy) return;
            Enemy->AutoPossessAI = EAutoPossessAI::Disabled;
            Enemy->EnemySkeletalMesh = Mesh;
            Enemy->IdleAnimation = Clip;
            Enemy->AttackAnimation = Clip;
            Enemy->FinishSpawning(Spawn);
            Enemy->SetActorTickEnabled(false);
            Enemy->GetEnemyBrain()->SetComponentTickEnabled(false);
            Enemy->GetCharacterMovement()->SetComponentTickEnabled(false);
            Enemy->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
            Enemy->GetMesh()->SetComponentTickEnabled(false);
            Enemy->Blade->SetComponentTickEnabled(false);
        }
        ~FWorld()
        {
            if (!World) return;
            World->EndPlay(EEndPlayReason::Quit);
            GEngine->DestroyWorldContext(World);
            World->DestroyWorld(false);
            GFrameCounter = SavedFrameCounter;
        }
        bool Ready() const { return Enemy && Enemy->GetMesh()->GetSingleNodeInstance(); }
        void AddCurve(float Speed=100.0f)
        {
            UCurveVector* Curve = NewObject<UCurveVector>(Enemy);
            for (int32 Axis=0; Axis<3; ++Axis)
            {
                const FKeyHandle Start = Curve->FloatCurves[Axis].AddKey(0,0);
                const FKeyHandle End = Curve->FloatCurves[Axis].AddKey(1.65f,Axis == 0 ? 1.65f*Speed : 0);
                Curve->FloatCurves[Axis].SetKeyInterpMode(Start,RCIM_Linear);
                Curve->FloatCurves[Axis].SetKeyInterpMode(End,RCIM_Linear);
            }
            Enemy->AttackRootMotionCurve = Curve;
        }
        UBoxComponent* AddWall()
        {
            AActor* Wall = World->SpawnActor<AActor>();
            UBoxComponent* Box = NewObject<UBoxComponent>(Wall);
            Wall->SetRootComponent(Box);
            Wall->AddInstanceComponent(Box);
            Box->InitBoxExtent(FVector(8,100,150));
            Box->SetCollisionObjectType(ECC_WorldStatic);
            Box->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
            Box->SetCollisionResponseToAllChannels(ECR_Block);
            Box->RegisterComponent();
            Box->SetWorldLocation(FVector(90,0,88));
            return Box;
        }
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLEnemyRootMotionClockTest,
    "Nilin.EnemyAnimation.RootTravel.AnimationClockAndFacing",NLEnemyRootMotionTests::Flags)
bool FNLEnemyRootMotionClockTest::RunTest(const FString& Parameters)
{
    NLEnemyRootMotionTests::FWorld F;
    if (!TestTrue(TEXT("Isolated native animation fixture is ready"),F.Ready())) return false;
    FNLAttackRootMotionTestAccess::Attack(F.Enemy);
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,1.0f);
    TestTrue(TEXT("Legacy attack without a curve does not translate its capsule"),F.Enemy->GetActorLocation().Equals(FVector(0,0,88),.01f));
    const auto HasMeshPrerequisite = [&F]()
    {
        return F.Enemy->PrimaryActorTick.GetPrerequisites().ContainsByPredicate([&F](const FTickPrerequisite& Prerequisite)
        {
            return Prerequisite.Get() == &F.Enemy->GetMesh()->PrimaryComponentTick;
        });
    };
    TestFalse(TEXT("Unconfigured legacy character retains its original tick ordering"),HasMeshPrerequisite());
    F.AddCurve();
    F.Enemy->SetActorRotation(FRotator(0,90,0));
    FNLAttackRootMotionTestAccess::Attack(F.Enemy);
    TestTrue(TEXT("Configured capsule travel waits for this frame's actual mesh animation clock"),HasMeshPrerequisite());
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,.25f);
    TestTrue(TEXT("Animation sample moves actor-local travel in the committed direction"),F.Enemy->GetActorLocation().Equals(FVector(0,25,88),.02f));
    F.Enemy->SetActorRotation(FRotator::ZeroRotator);
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,.5f);
    TestTrue(TEXT("A committed lunge does not curve around a moving target"),F.Enemy->GetActorLocation().Equals(FVector(0,50,88),.02f));
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,.5f);
    TestTrue(TEXT("Repeated sample cannot duplicate movement"),F.Enemy->GetActorLocation().Equals(FVector(0,50,88),.02f));
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,.1f);
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,1.2f);
    TestTrue(TEXT("Unexpected backwards seek cannot rewind or reapply a lunge"),F.Enemy->GetActorLocation().Equals(FVector(0,50,88),.02f));
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLEnemyRootMotionWallTest,
    "Nilin.EnemyAnimation.RootTravel.SweptWallAndNoBacklog",NLEnemyRootMotionTests::Flags)
bool FNLEnemyRootMotionWallTest::RunTest(const FString& Parameters)
{
    NLEnemyRootMotionTests::FWorld F;
    if (!TestTrue(TEXT("Isolated collision fixture is ready"),F.Ready())) return false;
    F.AddCurve();
    UBoxComponent* Wall = F.AddWall();
    FNLAttackRootMotionTestAccess::Attack(F.Enemy);
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,1.0f);
    const double BlockedX = F.Enemy->GetActorLocation().X;
    TestTrue(TEXT("Capsule sweep stops before the physical wall"),BlockedX > 45 && BlockedX < 55);
    Wall->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,1.2f);
    TestTrue(TEXT("Removing blocker permits only this sample's new travel"),FMath::IsNearlyEqual(F.Enemy->GetActorLocation().X,BlockedX+20.0,.02));
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLEnemyRootMotionCancellationTest,
    "Nilin.EnemyAnimation.RootTravel.CancelPauseDeathAndRetry",NLEnemyRootMotionTests::Flags)
bool FNLEnemyRootMotionCancellationTest::RunTest(const FString& Parameters)
{
    NLEnemyRootMotionTests::FWorld F;
    if (!TestTrue(TEXT("Isolated lifecycle fixture is ready"),F.Ready())) return false;
    F.AddCurve();
    FNLAttackRootMotionTestAccess::Attack(F.Enemy);
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,.25f);
    FNLAttackRootMotionTestAccess::Cancel(F.Enemy);
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,1.0f);
    TestTrue(TEXT("Cancelled attack has no late root travel"),FMath::IsNearlyEqual(F.Enemy->GetActorLocation().X,25.0,.02));
    FNLAttackRootMotionTestAccess::Attack(F.Enemy);
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,.25f);
    TestTrue(TEXT("New attack begins with a fresh curve baseline"),FMath::IsNearlyEqual(F.Enemy->GetActorLocation().X,50.0,.02));
    F.Enemy->SetLabPaused(true);
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,1.4f);
    F.Enemy->SetLabPaused(false);
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,1.5f);
    TestTrue(TEXT("Pause and resume cannot release cancelled attack displacement"),FMath::IsNearlyEqual(F.Enemy->GetActorLocation().X,50.0,.02));
    FNLAttackRootMotionTestAccess::Attack(F.Enemy);
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,.1f);
    FNLAttackRootMotionTestAccess::React(F.Enemy);
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,1.0f);
    TestTrue(TEXT("A nonattack one-shot never consumes the attack curve"),FMath::IsNearlyEqual(F.Enemy->GetActorLocation().X,60.0,.02));
    FNLAttackRootMotionTestAccess::Attack(F.Enemy);
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,.1f);
    FNLAttackRootMotionTestAccess::Die(F.Enemy);
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,1.0f);
    TestTrue(TEXT("Death stops authored root travel"),FMath::IsNearlyEqual(F.Enemy->GetActorLocation().X,70.0,.02));
    F.Enemy->ResetForEncounter();
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,1.0f);
    TestTrue(TEXT("Retry resets to spawn without stale displacement"),F.Enemy->GetActorLocation().Equals(FVector(0,0,88),.02f));
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLEnemyRootMotionAirborneTest,
    "Nilin.EnemyAnimation.RootTravel.AirbornePhysicsAndNoLandingBacklog",NLEnemyRootMotionTests::Flags)
bool FNLEnemyRootMotionAirborneTest::RunTest(const FString& Parameters)
{
    NLEnemyRootMotionTests::FWorld F;
    if (!TestTrue(TEXT("Isolated falling fixture is ready"),F.Ready())) return false;
    F.AddCurve();
    FNLAttackRootMotionTestAccess::Attack(F.Enemy);
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,.1f);
    UCharacterMovementComponent* Movement = F.Enemy->GetCharacterMovement();
    Movement->SetMovementMode(MOVE_Falling);
    Movement->Velocity = FVector(0,0,-200);
    const FVector BeforeFall = F.Enemy->GetActorLocation();
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,.8f);
    TestTrue(TEXT("Ground attack curve does not translate an airborne capsule"),F.Enemy->GetActorLocation().Equals(BeforeFall,.01));
    TestTrue(TEXT("Airborne curve sample preserves vertical physics velocity"),Movement->Velocity.Equals(FVector(0,0,-200),.01));
    Movement->bRunPhysicsWithNoController = true;
    Movement->SetComponentTickEnabled(true);
    ++GFrameCounter;
    F.World->Tick(LEVELTICK_All,.05f);
    TestTrue(TEXT("Real falling physics still accelerates downwards"),Movement->Velocity.Z < -200 && F.Enemy->GetActorLocation().Z < BeforeFall.Z);
    const FVector FallingVelocity = Movement->Velocity;
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,1.0f);
    TestTrue(TEXT("Subsequent attack sample cannot zero the accumulated falling velocity"),Movement->Velocity.Equals(FallingVelocity,.01));
    Movement->SetComponentTickEnabled(false);
    Movement->SetMovementMode(MOVE_Walking);
    const FVector Landing = F.Enemy->GetActorLocation();
    FNLAttackRootMotionTestAccess::Sample(F.Enemy,1.1f);
    TestTrue(TEXT("Landing applies only the new grounded sample, never skipped airborne travel"),
        F.Enemy->GetActorLocation().Equals(Landing+FVector(10,0,0),.02));
    return !HasAnyErrors();
}

#endif
