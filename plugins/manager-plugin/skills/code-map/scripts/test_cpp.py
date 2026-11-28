"""Tests for codemap.py on C, C++ and Unreal Engine code (`references/cpp.md`).

python3 -m unittest discover -s <this folder>
"""
import os
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
import portability  # noqa: E402  (in the plugin folder)
import codemap  # noqa: E402
from test_codemap import run  # noqa: E402

CLIB_H = (
    "#ifndef CLIB_H\n"                                       # 1
    "#define CLIB_H\n"                                       # 2
    "#include <stddef.h>\n"                                  # 3
    "#define CLIB_MAX(a, b) ((a) > (b) ? (a) : (b))\n"       # 4
    "#define CLIB_VERSION 3\n"                               # 5
    "typedef struct clib_ctx {\n"                            # 6
    "    int refs;\n"                                        # 7
    "} clib_ctx;\n"                                          # 8
    "typedef int (*clib_cb)(void *user, int code);\n"        # 9
    "#ifdef __cplusplus\n"                                   # 10
    "extern \"C\" {\n"                                       # 11
    "#endif\n"                                               # 12
    "int clib_open(clib_ctx *ctx,\n"                         # 13
    "              const char *name);\n"                     # 14
    "void clib_close(clib_ctx *ctx);\n"                      # 15
    "#ifdef __cplusplus\n"                                   # 16
    "}\n"                                                    # 17
    "#endif\n"                                               # 18
    "#if 0\n"                                                # 19
    "int clib_dead(void);\n"                                 # 20
    "#endif\n"                                               # 21
    "#endif\n")                                              # 22

CLIB_C = (
    "#include \"clib.h\"\n"                                  # 1
    "#include <string.h>\n"                                  # 2
    "#include \"missing/config.h\"\n"                        # 3
    "static int helper(int x);\n"                            # 4
    "/* int fake_comment(void) { } */\n"                     # 5
    "int clib_open(clib_ctx *ctx, const char *name)\n"       # 6
    "{\n"                                                    # 7
    "    const char *s = \"}{ clib_close(\";\n"              # 8
    "    char c = '}';\n"                                    # 9
    "    return helper((int)strlen(name));\n"                # 10
    "}\n"                                                    # 11
    "void clib_close(clib_ctx *ctx) { ctx->refs--; }\n"      # 12
    "#if 0\n"                                                # 13
    "int fake_dead(void) { return clib_close(0); }\n"        # 14
    "#endif\n"                                               # 15
    "static int helper(int x) { return x; }\n")              # 16

GEO_HPP = (
    "#pragma once\n"                                         # 1
    "#include <vector>\n"                                    # 2
    "namespace geo { namespace detail {\n"                   # 3
    "template <typename T>\n"                                # 4
    "struct Holder { T value; };\n"                          # 5
    "} }\n"                                                  # 6
    "namespace geo {\n"                                      # 7
    "enum class Kind : int { Circle, Square };\n"            # 8
    "class Shape\n"                                          # 9
    "{\n"                                                    # 10
    "public:\n"                                              # 11
    "    explicit Shape(Kind k) : kind_{k} {}\n"             # 12
    "    virtual ~Shape() = default;\n"                      # 13
    "    [[nodiscard]] virtual double area() const;\n"       # 14
    "    template <class U>\n"                               # 15
    "    static constexpr U scale(const U& u,\n"             # 16
    "                             double by) noexcept;\n"    # 17
    "private:\n"                                             # 18
    "    Kind kind_;\n"                                      # 19
    "};\n"                                                   # 20
    "using ShapeList = std::vector<Shape>;\n"                # 21
    "inline int twice(int x) { return 2 * x; }\n"            # 22
    "}\n"                                                    # 23
    "namespace geo::io {\n"                                  # 24
    "struct Writer { int fd; };\n"                           # 25
    "}\n")                                                   # 26

GEO_CPP = (
    "#include \"geo.hpp\"\n"                                 # 1
    "\n"                                                     # 2
    "namespace geo {\n"                                      # 3
    "\n"                                                     # 4
    "double Shape::area() const\n"                           # 5
    "{\n"                                                    # 6
    "    return twice(2) * 1.5;\n"                           # 7
    "}\n"                                                    # 8
    "\n"                                                     # 9
    "}  // namespace geo\n"                                  # 10
    "\n"                                                     # 11
    "static double total(const geo::ShapeList& shapes,\n"    # 12
    "                    double start)\n"                    # 13
    "{\n"                                                    # 14
    "    double sum = start;\n"                              # 15
    "    for (const auto& s : shapes) { sum += s.area(); }\n"  # 16
    "    return sum;\n"                                      # 17
    "}\n")                                                   # 18

USE_CPP = (
    "#include <geo/shapes.h>\n"     # under modern/include: followed
    "#include <geo.hpp>\n"          # modern/geo.hpp is not under an include folder: not followed
    "#include <cstdio>\n"
    "int use() { return area(); }\n")

NET_H = (
    "#pragma once\n"                                                         # 1
    "#include \"CoreMinimal.h\"\n"                                           # 2
    "#include \"MyNet.generated.h\"\n"                                       # 3
    "DECLARE_DELEGATE_RetVal_OneParam(bool, FCanFire, int32);\n"             # 4
    "DECLARE_DYNAMIC_DELEGATE_RetVal(int32, FGetAmmo);\n"                    # 5
    "UCLASS()\n"                                                             # 6
    "class MYGAME_API UMyNet : public UObject\n"                             # 7
    "{\n"                                                                    # 8
    "\tGENERATED_BODY()\n"                                                   # 9
    "public:\n"                                                              # 10
    "\tUFUNCTION(Server, Reliable, WithValidation)\n"                        # 11
    "\tvoid ServerFire(int32 Shots);\n"                                      # 12
    "\tUFUNCTION(BlueprintNativeEvent)\n"                                    # 13
    "\tvoid OnReady();\n"                                                    # 14
    "\tUMyNet() = default;\n"                                                # 15
    "\tUMyNet(const UMyNet&) = delete;\n"                                    # 16
    "\toperator bool() const { return true; }\n"                             # 17
    "};\n")                                                                  # 18

NET_CPP = (
    "#include \"MyNet.h\"\n"                                                 # 1
    "void UMyNet::ServerFire_Implementation(int32 Shots) {}\n"               # 2
    "bool UMyNet::ServerFire_Validate(int32 Shots) { return Shots > 0; }\n"  # 3
    "void UMyNet::OnReady_Implementation() {}\n"                             # 4
    "UMyNet::UMyNet(const UMyNet& Other) {}\n")                              # 5

CASCADE = (  # each line once made the lines after it vanish
    "auto name() -> std::string { return {}; }\n"                                    # 1
    "int after1() { return 1; }\n"                                                   # 2
    "auto loc() const -> const std::locale& { return l; }\n"                         # 3
    "int after2() { return 2; }\n"                                                   # 4
    "template <class T> auto get(T t) -> decltype(std::declval<T>()) { return t; }\n"  # 5
    "struct Cfg { int v; };\n"                                                       # 6
    "template <class T> void swap2(T& a) noexcept(noexcept(T(a))) { }\n"             # 7
    "int after3() { return 3; }\n"                                                   # 8
    "int *(pick)(void) { return 0; }\n"                                              # 9
    "int after4() { return 4; }\n"                                                   # 10
    "template <typename T, typename = std::enable_if_t<(sizeof(T) > 4)>>\n"          # 11
    "void big(T t) {}\n"                                                             # 12
    "int after5() { return 5; }\n"                                                   # 13
    "MYLIB_EXPORT template <typename T> class Box { T v; };\n"                       # 14
    "int after6() { return 6; }\n"                                                   # 15
    "void (*get_cb(void))(int) { return 0; }\n"                                      # 16
    "int after7() { return 7; }\n"                                                   # 17
    "decltype(auto) ref(Foo& f) { return f.x; }\n"                                   # 18
    "SOME_MACRO(x) weird thing() junk { }\n"                                         # 19
    "int after8() { return 8; }\n"                                                   # 20
    "class K {\n"                                                                    # 21
    " public:\n"                                                                     # 22
    "  auto size() const -> std::size_t { return 0; }\n"                             # 23
    "  void reset() {}\n"                                                            # 24
    "  operator bool() const { return true; }\n"                                     # 25
    "  int count() const { return 1; }\n"                                            # 26
    "};\n")                                                                          # 27

BUILD_CS = (
    "using UnrealBuildTool;\n"
    "\n"
    "public class MyGame : ModuleRules\n"
    "{\n"
    "\tpublic MyGame(ReadOnlyTargetRules Target) : base(Target)\n"
    "\t{\n"
    "\t\tPublicDependencyModuleNames.AddRange(new string[] {\n"
    "\t\t\t\"Core\", \"CoreUObject\", \"Engine\", // the basics\n"
    "\t\t\t\"MyTools\" });\n"
    "\t\tPrivateDependencyModuleNames.Add(\"Slate\");\n"
    "\t\t// PrivateDependencyModuleNames.Add(\"Commented\");\n"
    "\t}\n"
    "}\n")

ACTOR_H = (
    "#pragma once\n"                                                     # 1
    "\n"                                                                 # 2
    "#include \"CoreMinimal.h\"\n"                                       # 3
    "#include \"GameFramework/Actor.h\"\n"                               # 4
    "#include \"MyTypes.h\"\n"                                           # 5
    "#include \"MyActor.generated.h\"\n"                                 # 6
    "\n"                                                                 # 7
    "DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnHit, float, Damage);\n"  # 8
    "\n"                                                                 # 9
    "UCLASS(Blueprintable)\n"                                            # 10
    "class MYGAME_API AMyActor : public AActor\n"                        # 11
    "{\n"                                                                # 12
    "\tGENERATED_BODY()\n"                                               # 13
    "\n"                                                                 # 14
    "public:\n"                                                          # 15
    "\tAMyActor();\n"                                                    # 16
    "\n"                                                                 # 17
    "\tUFUNCTION(BlueprintCallable, Category = \"Combat\")\n"            # 18
    "\tvoid Fire(float Power);\n"                                        # 19
    "\n"                                                                 # 20
    "\tUPROPERTY(BlueprintAssignable)\n"                                 # 21
    "\tFOnHit OnHit;\n"                                                  # 22
    "\n"                                                                 # 23
    "\tint32 GetAmmo() const { return Ammo; }\n"                         # 24
    "\n"                                                                 # 25
    "protected:\n"                                                       # 26
    "\tvirtual void BeginPlay() override;\n"                             # 27
    "\n"                                                                 # 28
    "\tUFUNCTION()\n"                                                    # 29
    "\tvoid HandleHit(float Damage);\n"                                  # 30
    "\n"                                                                 # 31
    "private:\n"                                                         # 32
    "\tUPROPERTY(EditAnywhere)\n"                                        # 33
    "\tint32 Ammo = 3;\n"                                                # 34
    "};\n")                                                              # 35

ACTOR_CPP = (
    "#include \"MyActor.h\"\n"                                           # 1
    "#include \"ToolLib.h\"\n"                                           # 2
    "#include \"Kismet/GameplayStatics.h\"\n"                            # 3
    "\n"                                                                 # 4
    "AMyActor::AMyActor()\n"                                             # 5
    "{\n"                                                                # 6
    "\tPrimaryActorTick.bCanEverTick = false;\n"                         # 7
    "}\n"                                                                # 8
    "\n"                                                                 # 9
    "void AMyActor::Fire(float Power)\n"                                 # 10
    "{\n"                                                                # 11
    "\tif (Power > 0) { OnHit.Broadcast(Power); }\n"                     # 12
    "\tUE_LOG(LogMyGame, Log, TEXT(\"Fire %f\"), Power);\n"              # 13
    "}\n"                                                                # 14
    "\n"                                                                 # 15
    "void AMyActor::BeginPlay()\n"                                       # 16
    "{\n"                                                                # 17
    "\tSuper::BeginPlay();\n"                                            # 18
    "\tOnHit.AddDynamic(this, &AMyActor::HandleHit);\n"                  # 19
    "\tFTimerHandle Handle;\n"                                           # 20
    "\tGetWorldTimerManager().SetTimer(Handle, this, &AMyActor::Fire, 1.0f);\n"  # 21
    "\tFTimerDelegate Later;\n"                                          # 22
    "\tLater.BindUFunction(this, FName(\"Fire\"));\n"                    # 23
    "\tUToolLib::Help(this);\n"                                          # 24
    "}\n"                                                                # 25
    "\n"                                                                 # 26
    "void AMyActor::HandleHit(float Damage)\n"                           # 27
    "{\n"                                                                # 28
    "\tFire(Damage);\n"                                                  # 29
    "}\n")                                                               # 30

TYPES_H = (
    "#pragma once\n"
    "#include \"CoreMinimal.h\"\n"
    "#include \"MyTypes.generated.h\"\n"
    "\n"
    "DECLARE_LOG_CATEGORY_EXTERN(LogMyGame, Log, All);\n"
    "\n"
    "UENUM(BlueprintType)\n"
    "enum class EWeapon : uint8\n"
    "{\n"
    "\tSword UMETA(DisplayName = \"Sword\"),\n"
    "\tBow\n"
    "};\n"
    "\n"
    "USTRUCT(BlueprintType)\n"
    "struct FWeaponData\n"
    "{\n"
    "\tGENERATED_BODY()\n"
    "\n"
    "\tUPROPERTY(EditAnywhere, BlueprintReadWrite)\n"
    "\tint32 Rounds = 0;\n"
    "};\n")

GAME_CPP = (
    "#include \"MyTypes.h\"\n"
    "#include \"Modules/ModuleManager.h\"\n"
    "\n"
    "DEFINE_LOG_CATEGORY(LogMyGame);\n"
    "IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, MyGame, \"MyGame\");\n")

TOOL_H = (
    "#pragma once\n"
    "#include \"CoreMinimal.h\"\n"
    "#include \"Kismet/BlueprintFunctionLibrary.h\"\n"
    "#include \"ToolLib.generated.h\"\n"
    "\n"
    "UCLASS()\n"
    "class MYTOOLS_API UToolLib : public UBlueprintFunctionLibrary\n"
    "{\n"
    "\tGENERATED_BODY()\n"
    "public:\n"
    "\tUFUNCTION(BlueprintPure, Category = \"Tools\")\n"
    "\tstatic int32 Help(UObject* Context);\n"
    "};\n")

TOOL_CPP = (
    "#include \"ToolLib.h\"\n"
    "\n"
    "int32 UToolLib::Help(UObject* Context)\n"
    "{\n"
    "\treturn Context ? 1 : 0;\n"
    "}\n")


def write(root, rel, data):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def make_fixture(root):
    """A plain C library, modern C++ and a small Unreal project with a plugin, in one git
    repository (nothing committed; the files are added to the index)."""
    for rel, data in (
            ("clib/include/clib.h", CLIB_H), ("clib/src/clib.c", CLIB_C),
            ("modern/geo.hpp", GEO_HPP), ("modern/geo.cpp", GEO_CPP),
            ("MyGame.uproject", '{"FileVersion": 3, "Modules": [{"Name": "MyGame"}]}\n'),
            ("Source/MyGame/MyGame.Build.cs", BUILD_CS),
            ("Source/MyGame/Public/MyActor.h", ACTOR_H),
            ("Source/MyGame/Private/MyActor.cpp", ACTOR_CPP),
            ("Source/MyGame/Public/MyTypes.h", TYPES_H),
            ("Source/MyGame/Private/MyGame.cpp", GAME_CPP),
            ("Source/MyGame/Public/MyNet.h", NET_H), ("Source/MyGame/Private/MyNet.cpp", NET_CPP),
            ("modern/use.cpp", USE_CPP),
            ("modern/include/geo/shapes.h", "#pragma once\nint area();\n"),
            ("Plugins/MyTools/MyTools.uplugin", '{"FileVersion": 3}\n'),
            ("Plugins/MyTools/Source/MyTools/MyTools.Build.cs",
             BUILD_CS.replace("MyGame", "MyTools").replace('"MyTools" });', '"Core" });')),
            ("Plugins/MyTools/Source/MyTools/Public/ToolLib.h", TOOL_H),
            ("Plugins/MyTools/Source/MyTools/Private/ToolLib.cpp", TOOL_CPP),
            ("Intermediate/Build/Win64/MyActor.generated.h", "void generated_only();\n"),
            ("Binaries/Win64/Game.h", "void binary_only();\n"),
            ("Plugins/MyTools/Intermediate/Gen.h", "void plugin_generated();\n"),
            ("Saved/Logs/x.cpp", "void saved_only() {}\n"),
            ("Content/BP_Actor.uasset", b"\x00\x01binary AMyActor Fire\x00"),
            ("Content/Main.umap", b"\x00\x02binary\x00")):
        write(root, rel, data)
    subprocess.run(["git", "init", "-q", root], check=True)
    subprocess.run(["git", "-C", root, "add", "-A"], check=True)


class CppTest(unittest.TestCase):
    def setUp(self):
        self.tmp = portability.temp_dir()
        self.root = self.tmp.name
        make_fixture(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def run_ok(self, *args):
        code, out = run(*args, "--root", self.root)
        self.assertEqual(code, 0, out)
        return out

    def page(self):
        self.run_ok("build")
        with open(os.path.join(self.root, "docs", "code-map.md"), encoding="utf-8") as fh:
            return fh.read()

    def entry_line(self, page, path):
        lines = [x for x in page.split("\n") if x.startswith("- `%s` —" % path)
                 and "imported by" not in x]
        self.assertEqual(len(lines), 1, page)
        return lines[0]

    def test_symbols_on_the_page(self):
        page = self.page()
        self.assertEqual(self.entry_line(page, "clib/include/clib.h"),
                         "- `clib/include/clib.h` — clib_ctx, clib_cb, clib_open, clib_close, "
                         "CLIB_MAX, CLIB_VERSION")  # no clib_dead (`#if 0`), no guard; macros last
        self.assertEqual(self.entry_line(page, "clib/src/clib.c"),
                         "- `clib/src/clib.c` — clib_open, clib_close, helper")
        self.assertEqual(self.entry_line(page, "modern/geo.cpp"),
                         "- `modern/geo.cpp` — Shape::area, total, geo")
        self.assertIn("- `Source/MyGame/Public/MyActor.h` — FOnHit, AMyActor [UCLASS "
                      "Blueprintable], AMyActor::Fire [UFUNCTION BlueprintCallable], "
                      "AMyActor::OnHit [UPROPERTY BlueprintAssignable], AMyActor::HandleHit "
                      "[UFUNCTION]\n", page)
        self.assertIn("- `Source/MyGame/Public/MyTypes.h` — LogMyGame, EWeapon [UENUM "
                      "BlueprintType], FWeaponData [USTRUCT BlueprintType], FWeaponData::Rounds "
                      "[UPROPERTY BlueprintReadWrite]\n", page)
        self.assertIn("- `Source/MyGame/Private/MyGame.cpp` — LogMyGame\n", page)
        for gone in ("generated_only", "binary_only", "plugin_generated", "saved_only",
                     "Intermediate", "fake_comment", "fake_dead", "clib_dead"):
            self.assertNotIn(gone, page.split("## Unreal Engine")[0] + page.split(
                "Blueprint and level references")[1])

    def test_modern_symbols(self):
        with open(os.path.join(self.root, "modern", "geo.hpp"), encoding="utf-8") as fh:
            cf = codemap.CppFile("modern/geo.hpp", fh.read())
        got = [("::".join(s["qual"]), s["kind"], s["line"], s["start"], s["end"])
               for s in cf.symbols]
        self.assertTrue(cf.clean)
        self.assertEqual(got, [
            ("geo", "namespace", 3, 3, 6), ("geo::detail", "namespace", 3, 3, 6),
            ("geo::detail::Holder", "struct", 5, 4, 5), ("geo", "namespace", 7, 7, 23),
            ("geo::Kind", "enum class", 8, 8, 8), ("geo::Shape", "class", 9, 9, 20),
            ("geo::Shape::Shape", "method", 12, 12, 12),
            ("geo::Shape::~Shape", "defaulted method", 13, 13, 13),
            ("geo::Shape::area", "method declaration", 14, 14, 14),
            ("geo::Shape::scale", "method declaration", 16, 15, 17),
            ("geo::ShapeList", "using", 21, 21, 21), ("geo::twice", "function", 22, 22, 22),
            ("geo::io", "namespace", 24, 24, 26), ("geo::io::Writer", "struct", 25, 25, 25)])

    def test_query_kinds_and_declarations(self):
        out = self.run_ok("query", "clib_open")
        self.assertIn("  clib/include/clib.h:13 clib_open (function declaration)\n", out)
        self.assertIn("  clib/src/clib.c:6 clib_open (function)\n", out)
        out = self.run_ok("query", "Fire")
        self.assertIn("MyActor.cpp:10 AMyActor::Fire (method; UFUNCTION BlueprintCallable)", out)

    def test_pairing_direction_scope_and_overloads(self):
        h = codemap.CppFile("p.h", "namespace a { void f(); }\nvoid g(int x);\n"
                                   "void g(int x, int y);\nvoid k(int x);\n"
                                   "namespace a { void h(); }\nvoid h();\n")
        c = codemap.CppFile("p.cpp", "void f() {}\nvoid g(int x, int y) {}\nvoid k() {}\n"
                                     "void g() {}\nnamespace a { void h() {} }\n")
        codemap.cpp_link({"p.h": h, "p.cpp": c})
        got = {(s["name"], s["line"]): [(d["path"], d["line"]) for d in s.get("declared", ())]
               for s in c.symbols if not s["decl"]}
        self.assertEqual(got, {
            ("f", 1): [],                  # top level: not the `a::f` declaration
            ("g", 2): [("p.h", 3)],        # the overload with two parameters
            ("k", 3): [("p.h", 4)],        # the only candidate, whatever its parameters
            ("g", 4): [],                  # two overloads, neither without parameters
            ("a", 5): [], ("h", 5): [("p.h", 5)]})  # `a::h`, not the top-level `h`

    def test_default_arguments_requires_and_lowercase_tails(self):
        cf = codemap.CppFile("d.cpp", "void f1(int a = 0) __THROW { }\nvoid f2() { }\n"
                                      "static void f4(int b = 1) __wur { }\n"
                                      "int f6(int c = 2) const_fn { return 0; }\nvoid f7() { }\n"
                                      "void z(int a = 0) __nonnull((1)) _NOEXCEPT { }\n"
                                      "template <class T>\nrequires std::integral<T> && "
                                      "(sizeof(T) > 2)\nT twice(T x) { return x; }\n"
                                      "template <class T> requires Small<T>\nstruct Box { };\n"
                                      "int after() { return 0; }\n")
        self.assertEqual([(s["name"], s["line"], s["start"]) for s in cf.symbols], [
            ("f1", 1, 1), ("f2", 2, 2), ("f4", 3, 3), ("f7", 5, 5), ("z", 6, 6),
            ("twice", 9, 7), ("Box", 11, 10), ("after", 12, 12)])  # `const_fn`: unclassified

    def test_brace_initializer_chain_is_linear(self):
        for n in (4000, 16000):
            text = "int a0{1}" + "".join(", a%d{1}" % i for i in range(1, n)) + ";\nint z() {}\n"
            t = time.perf_counter()
            cf = codemap.CppFile("b.cpp", text)
            self.assertLess(time.perf_counter() - t, 1.0, n)
            self.assertEqual([s["name"] for s in cf.symbols], ["z"])

    def test_destructor_and_operator_names(self):
        write(self.root, "modern/ops.hpp", "struct V {\n  bool operator==(const V& o) const;\n"
                                           "  ~V();\n};\n")
        write(self.root, "modern/ops.cpp", "#include \"ops.hpp\"\n"
                                           "bool V::operator==(const V& o) const { return true; }\n"
                                           "V::~V() {}\n")
        subprocess.run(["git", "-C", self.root, "add", "-A"], check=True)
        for name, head in (("~V", "modern/ops.cpp:3-3 method V::~V"),
                           ("V::~V", "modern/ops.cpp:3-3 method V::~V"),
                           ("~ V", "modern/ops.cpp:3-3 method V::~V"),
                           ("operator==", "modern/ops.cpp:2-2 method V::operator=="),
                           ("V::operator ==", "modern/ops.cpp:2-2 method V::operator==")):
            out = self.run_ok("explore", name)
            self.assertIn(head, out)
            out = self.run_ok("calls", name)
            self.assertIn("definitions:\n  %s %s (C++ method)" % (
                head.split()[0].split("-")[0], head.split()[2]), out)

    def test_calls_wording_for_cpp_only_names(self):
        out = self.run_ok("calls", "Fire")
        self.assertIn("\ncoverage: C/C++ calls are not resolved: ", out)
        self.assertNotIn("static Python calls", out)
        self.assertNotIn("not parsed as Python", out)

    def test_definition_in_a_class_body_pairs_only_with_its_own_class(self):
        h = codemap.CppFile("n.h", "struct Node { ~Node(); void f(); };\n")
        c = codemap.CppFile("c.h", "namespace c { struct Node { ~Node() {} void f() {} }; }\n"
                                   "Node::~Node() {}\n")
        codemap.cpp_link({"n.h": h, "c.h": c})
        got = {("::".join(s["qual"]), s["line"]): len(s.get("declared", ()))
               for s in c.symbols if s["kind"] == "method"}
        self.assertEqual(got, {("c::Node::~Node", 1): 0, ("c::Node::f", 1): 0,
                               ("Node::~Node", 2): 1})

    def test_rpc_declaration_names_its_bodies(self):
        out = self.run_ok("explore", "ServerFire")
        self.assertIn("MyNet.h:11-12 method declaration UMyNet::ServerFire [UFUNCTION Server] "
                      "(bodies: ServerFire_Implementation, ServerFire_Validate)\n", out)

    def test_hidden_friend_is_a_namespace_function(self):
        h = codemap.CppFile("k.h", "namespace n {\nstruct FKey {\n  int A;\n"
                                   "  friend unsigned GetTypeHash(const FKey& K) { return K.A; }\n"
                                   "  bool Same(const FKey& K) const { return true; }\n};\n"
                                   "unsigned GetTypeHash(const FKey& K);\n}\n")
        codemap.cpp_link({"k.h": h})
        got = {("::".join(s["qual"]), s["kind"], s["parent"] is None): len(s.get("declared", ()))
               for s in h.symbols if s["name"] in ("GetTypeHash", "Same")}
        self.assertEqual(got, {("n::GetTypeHash", "function", True): 1,
                               ("n::GetTypeHash", "function declaration", True): 0,
                               ("n::FKey::Same", "method", False): 0})

    def test_macro_call_before_the_name(self):
        cf = codemap.CppFile("hb.c", "static inline void HB_PRINTF_FUNC(7, 8)\n"
                                     "_hb_debug_msg(const char *what, int level)\n{\n}\n"
                                     "void UE_DEPRECATED(5.1, \"x\") Old(int a);\n")
        self.assertEqual([(s["name"], s["kind"]) for s in cf.symbols],
                         [("_hb_debug_msg", "function"), ("Old", "function declaration")])

    def test_comment_inside_a_define_keeps_it_going(self):
        cf = codemap.CppFile("m.c", "#define BEGIN(x) \\\n  do { /* open a \\\n"
                                    "  scope */ \\\n    x; \\\n  } while (0)\n"
                                    "int after_macro(void) { return 1; }\n")
        self.assertEqual([(s["name"], s["kind"]) for s in cf.symbols],
                         [("BEGIN", "macro"), ("after_macro", "function")])
        self.assertTrue(cf.clean)

    def test_stopped_scan_named_by_explore_and_calls(self):
        write(self.root, "modern/stop.c", "int good(void) { return 1; }\nint broken(void) {\n"
                                          "  if (x) {\n  return 0;\n}\n"
                                          "int lost(void) { return good(); }\n")
        subprocess.run(["git", "-C", self.root, "add", "-A"], check=True)
        note = ("scan stopped in modern/stop.c (line 2), before a line naming it (a bracket "
                "never closes; definitions after that line are not read)")
        self.assertIn("; %s); near matches:" % note, self.run_ok("explore", "lost"))
        self.assertIn("\n%s\n" % note, self.run_ok("calls", "lost"))
        self.assertNotIn("scan stopped", self.run_ok("calls", "clib_open"))

    def test_implicit_calls_and_shell_safe_hints(self):
        write(self.root, "modern/ops.hpp", "struct V {\n  V();\n  ~V();\n"
                                           "  explicit operator bool() const;\n};\n")
        write(self.root, "modern/ops.cpp", "#include \"ops.hpp\"\nV::V() {}\nV::~V() {}\n"
                                           "V::operator bool() const { return true; }\n")
        subprocess.run(["git", "-C", self.root, "add", "-A"], check=True)
        for name, why in (("~V", "destructors run implicitly"),
                          ("operator  bool", "operators are mostly called implicitly"),
                          ("V::V", "constructors run implicitly")):
            out = self.run_ok("calls", name)
            self.assertIn("; %s" % why, out.split("\ntext: ")[1].split("\n")[0])
            if "\npossible: none found" in out:
                self.assertIn("\npossible: none found (%s" % why, out)
        out = self.run_ok("explore", "operator  bool")
        self.assertIn("modern/ops.cpp:4-4 method V::operator bool", out)
        self.assertIn("run calls 'operator bool' (text occurrences) or grep -n -F -w "
                      "'operator bool'\n", out)
        self.assertIn("run calls '~V' (text occurrences) or grep -n -F -w '~V'\n",
                      self.run_ok("explore", "~V"))
        self.assertIn("; named without a call at ", self.run_ok("calls", "V::V"))
        self.assertNotIn("passed or stored", self.run_ok("calls", "V::V"))

    def test_includes_counted_and_resolved(self):
        page = self.page()
        self.assertIn("9 `#include` lines resolved to tracked files (`\"...\"`, and `<...>` under "
                      "the project's include folders). Not followed, only counted: 4 `<...>` "
                      "includes not found there, 13 `\"...\"` includes not found among the "
                      "tracked files (engine, system or generated headers), 0 computed "
                      "(`#include MACRO`). Not found most often: `*.generated.h` (4), "
                      "`CoreMinimal.h` (4)", page)
        self.assertIn(" 1 more name a path that ends a tracked file's path but is under no "
                      "include folder this tool reads", page)  # `<geo.hpp>`
        self.assertIn("- `Plugins/MyTools/Source/MyTools/Public/ToolLib.h` — imported by 2 files",
                      page)  # from its own module and, through the module roots, from MyGame
        self.assertIn("## Most imported (Python, JavaScript and TypeScript local imports, C and "
                      "C++ `#include`s)", page)
        out = self.run_ok("query", "MyActor.h")
        self.assertIn("  Source/MyGame/Public/MyActor.h (imported by 1 local files; 3 of its "
                      "includes not followed)\n    <- Source/MyGame/Private/MyActor.cpp\n", out)

    def test_angle_includes(self):
        out = self.run_ok("impact", "modern/include/geo/shapes.h")
        self.assertIn("  imported by: modern/use.cpp\n", out)
        out = self.run_ok("impact", "modern/geo.hpp")
        self.assertIn("  imported by: modern/geo.cpp\n", out)
        self.assertIn("  not followed: possibly imported by modern/use.cpp (an `#include` path "
                      "found under no include folder read, ending only this file's path)\n", out)
        out = self.run_ok("query", "geo.hpp")
        self.assertIn("  modern/geo.hpp (imported by 1 local files; 1 of its includes not "
                      "followed)\n    <- modern/geo.cpp\n"
                      "    possibly imported by modern/use.cpp (not followed: an unresolved "
                      "`#include` ends this path)\n", out)

    def test_unbalanced_keeps_the_scan_that_read_further(self):
        text = ("#if X\nint g() {}\n#else\nint g(x, {\n#endif\nint c() {}\n"
                "namespace n {\nint d() {}\n")  # every branch: stops at 4; the first: to the end
        cf = codemap.CppFile("u.cpp", text)
        self.assertEqual((cf.clean, cf.stopped), (False, None))
        self.assertEqual([s["name"] for s in cf.symbols], ["g", "c", "n", "d"])
        cf = codemap.CppFile("v.cpp", "int a() {}\nint g(x, {\nint c() {}\n")
        self.assertEqual((cf.clean, cf.stopped, [s["name"] for s in cf.symbols]),
                         (False, 2, ["a"]))
        self.assertIn("(end approximate: braces do not balance in this file; scan stopped at "
                      "line 2)", codemap.cpp_entry(cf, cf.symbols[0])["note"])
        info = {"v.cpp": {"symbols": [("a", 1)], "stopped": 2}}
        self.assertEqual(codemap.file_lines(info, ["v.cpp"], "codemap.py"),
                         ["- `v.cpp` — a (scan stopped at line 2: a bracket never closes)"])

    def test_tails_never_backtrack(self):
        """Macro words, `__attribute__((...))` and `__declspec(...)` after a parameter list:
        matched or refused at once, each word whole."""
        tails = (" ABSL_MUST_USE_RESULT_AND_LIFETIME_BOUND_ATTRIBUTE_X" * 6 + " x",
                 ' ENGINE_DEPRECATED(5.1, "Use the other one") CONST_QUALIFIED_THING' * 6 + " +",
                 " __attribute__((nonnull(1, 2))) __declspec(dllexport)" * 8 + " ?")
        for tail in tails:
            for rx in (codemap.C_TAIL_DEF, codemap.C_TAIL_DECL):
                t = time.perf_counter()
                self.assertIsNone(rx.match(tail.lstrip()))
                self.assertLess(time.perf_counter() - t, 1.0, tail)
        for text in ("A<B>::" * 25 + "x y z(int a) {}\n",
                     "int f(int a)" + tails[0] + ";\nint g() {}\n",
                     "template <class T> struct S" + "<T" * 30 + " {};\nint h() {}\n",
                     "void " + "A<(b) c>::" * 200 + "f(int) {}\n",
                     "class " + "N<x>::" * 500 + "M<y> : public B {};\n"):
            t = time.perf_counter()
            codemap.CppFile("p.cpp", text)
            self.assertLess(time.perf_counter() - t, 1.0, text)
        cf = codemap.CppFile("p.cpp", 'void F() const ENGINE_DEPRECATED(5.1, "Use G") '
                                      "ABSL_ATTRIBUTE_LIFETIME_BOUND __attribute__((pure)) {}\n"
                                      "int G(int a) __declspec(noinline) noexcept;\n")
        self.assertEqual([(s["name"], s["kind"]) for s in cf.symbols],
                         [("F", "function"), ("G", "function declaration")])

    def test_deep_template_specialisations(self):
        cf = codemap.CppFile("r.h", "template <typename R>\nstruct formatter<\n    R, char,\n"
                                    "    enable_if_t<bool_constant<kind<R, char>::value != 0 &&\n"
                                    "        is_fmt<wrap<R>>::value>::value>> {\n"
                                    "  void parse(int x) {}\n};\n")
        self.assertEqual([(s["qual"], s["line"]) for s in cf.symbols],
                         [(["formatter"], 2), (["formatter", "parse"], 6)])

    def test_names_never_hold_line_breaks(self):
        cf = codemap.CppFile("t.cpp", "template <>\nvoid Box<int,\n  std::map<int, int>>::"
                                      "put(int a) {}\ntemplate <typename T>\nstruct Spec<T,\n"
                                      "  int> { int z; };\nvoid Outer<A<B>>::Inner<C>::go() {}\n")
        self.assertEqual([(s["qual"], s["kind"]) for s in cf.symbols], [
            (["Box", "put"], "function"), (["Spec"], "struct"),
            (["Outer", "Inner", "go"], "function")])

    def test_cascade_triggers_hide_nothing(self):
        cf = codemap.CppFile("c.cpp", CASCADE)
        self.assertTrue(cf.clean)
        got = {"::".join(s["qual"]): s["line"] for s in cf.symbols}
        for name, n in (("name", 1), ("after1", 2), ("loc", 3), ("after2", 4), ("get", 5),
                        ("Cfg", 6), ("swap2", 7), ("after3", 8), ("pick", 9), ("after4", 10),
                        ("big", 12), ("after5", 13), ("Box", 14), ("after6", 15),
                        ("get_cb", 16), ("after7", 17), ("ref", 18), ("after8", 20),
                        ("K", 21), ("K::size", 23), ("K::reset", 24), ("K::operator bool", 25),
                        ("K::count", 26)):
            self.assertEqual(got.get(name), n, (name, got))
        k = [s for s in cf.symbols if s["name"] == "K"][0]
        e = codemap.cpp_entry(cf, k)
        self.assertEqual([m["name"] for m in e["members"]],
                         ["K::size", "K::reset", "K::operator bool", "K::count"])
        self.assertEqual([(s["start"], s["end"]) for s in cf.symbols if s["name"] == "big"],
                         [(11, 12)])

    def test_unreal_rpc_retval_and_special_members(self):
        with open(os.path.join(self.root, "Source/MyGame/Public/MyNet.h"), encoding="utf-8") as fh:
            cf = codemap.CppFile("Source/MyGame/Public/MyNet.h", fh.read())
        kinds = {"::".join(s["qual"]): s["kind"] for s in cf.symbols}
        self.assertEqual(kinds["FCanFire"], "delegate")
        self.assertEqual(kinds["FGetAmmo"], "dynamic delegate")
        self.assertNotIn("bool", kinds)
        self.assertEqual(kinds["UMyNet::UMyNet"], "deleted method")
        self.assertEqual(kinds["UMyNet::operator bool"], "method")
        out = self.run_ok("explore", "ServerFire")
        self.assertIn("explore ServerFire: 3 definitions in 2 files\n", out)
        self.assertIn("Source/MyGame/Private/MyNet.cpp:2-2 method "
                      "UMyNet::ServerFire_Implementation [UFUNCTION Server] (declared "
                      "Source/MyGame/Public/MyNet.h:12)", out)
        self.assertIn("Source/MyGame/Private/MyNet.cpp:3-3 method UMyNet::ServerFire_Validate", out)
        out = self.run_ok("explore", "OnReady")
        self.assertIn("MyNet.cpp:4-4 method UMyNet::OnReady_Implementation [UFUNCTION "
                      "BlueprintNativeEvent]", out)
        out = self.run_ok("explore", "UMyNet::UMyNet")  # not paired with `= delete`
        self.assertIn("Source/MyGame/Private/MyNet.cpp:5-5 method UMyNet::UMyNet\n", out)
        self.assertIn("Source/MyGame/Public/MyNet.h:16-16 deleted method UMyNet::UMyNet\n", out)
        self.assertNotIn("no definition", out)

    def test_impact(self):
        out = self.run_ok("impact", "Source/MyGame/Public/MyTypes.h")
        self.assertIn("  imported by: Source/MyGame/Private/MyGame.cpp, "
                      "Source/MyGame/Public/MyActor.h\n", out)
        self.assertIn("  depth 2: Source/MyGame/Private/MyActor.cpp\n", out)
        out = self.run_ok("impact", "clib/include/clib.h")
        self.assertIn("  imported by: clib/src/clib.c\n", out)

    def test_changed_definitions(self):
        git = ["git", "-C", self.root, "-c", "user.name=t", "-c", "user.email=t@example.com"]
        subprocess.run(git + ["commit", "-qm", "one"], check=True)
        path = os.path.join(self.root, "Plugins/MyTools/Source/MyTools/Private/ToolLib.cpp")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        write(self.root, "Plugins/MyTools/Source/MyTools/Private/ToolLib.cpp",
              text.replace("1 : 0", "2 : 0"))
        subprocess.run(git + ["commit", "-qam", "two"], check=True)
        out = self.run_ok("changed", "--base", "HEAD~1", "--head", "HEAD")
        self.assertIn("M Plugins/MyTools/Source/MyTools/Private/ToolLib.cpp\n"
                      "  definitions: UToolLib::Help\n", out)

    def test_export_macros(self):
        cf = codemap.CppFile("lib.h", "class MYLIB_EXPORT Node : public Base { int f(); };\n"
                                      "MYLIB_PUBLIC(const char *) lib_version(void);\n"
                                      "TEST(Suite, Case) { lib_version(); }\n")
        self.assertEqual([("::".join(s["qual"]), s["kind"]) for s in cf.symbols],
                         [("Node", "class"), ("Node::f", "method declaration"),
                          ("lib_version", "function declaration")])

    def test_unreal_section(self):
        page = self.page()
        self.assertIn("projects: `MyGame.uproject`; plugins: `Plugins/MyTools/MyTools.uplugin`.",
                      page)
        self.assertIn("- `MyGame` (`Source/MyGame`) → public: Core, CoreUObject, Engine, MyTools; "
                      "private: Slate\n", page)
        self.assertIn("- `MyTools` (`Plugins/MyTools/Source/MyTools`) → public: Core, "
                      "CoreUObject, Engine; private: Slate\n", page)
        self.assertNotIn("Commented", page)
        self.assertIn("of the project and its plugins (4 tracked files).", page)
        self.assertIn("Binary assets (`.uasset`, `.umap`: 2 tracked files) are never read: "
                      "Blueprint and level references to C++ are not seen.", page)
        self.assertNotIn("Intermediate/Build", self.run_ok("query", "generated_only"))

    def test_no_unreal_without_project_files(self):
        out = codemap.unreal_filter(["Intermediate/a.h", "src/b.c"])
        self.assertEqual(out, (["Intermediate/a.h", "src/b.c"], 0))

    def test_explore_exact_ranges(self):
        out = self.run_ok("explore", "AMyActor::Fire")
        self.assertIn("Source/MyGame/Private/MyActor.cpp:10-14 method AMyActor::Fire [UFUNCTION "
                      "BlueprintCallable] (declared Source/MyGame/Public/MyActor.h:19)\n", out)
        self.assertIn("explore AMyActor::Fire: 1 definition in 1 file\n", out)  # as typed
        self.assertIn("callers: not resolved for C/C++; run calls AMyActor::Fire (text "
                      "occurrences) or grep -n -w Fire\n", out)
        out = self.run_ok("explore", "clib_open")
        self.assertIn("clib/src/clib.c:6-11 function clib_open (declared clib/include/clib.h:13)\n"
                      " 6\tint clib_open(", out)  # braces in strings and chars skipped
        out = self.run_ok("explore", "total")
        self.assertIn("modern/geo.cpp:12-18 function total\n", out)
        out = self.run_ok("explore", "AMyActor")  # the class, not its constructor
        self.assertIn("explore AMyActor: 1 definition in 1 file\n"
                      "Source/MyGame/Public/MyActor.h:10-35 class AMyActor [UCLASS Blueprintable]",
                      out)

    def test_explore_no_source_no_closing_line(self):
        out = self.run_ok("explore", "AMyActor", "--budget", "300")
        self.assertIn("body not shown: read Source/MyGame/Public/MyActor.h:10-35\n", out)
        self.assertNotIn("the source above", out)

    def test_explore_class_members(self):
        text = "class Big {\npublic:\n" + "".join(
            "    int f%d() {\n%s    }\n" % (i, "        x++;\n" * 8) for i in range(3)) + "};\n"
        text += "int Big::g() { return 1; }\n"
        cf = codemap.CppFile("big.h", text)
        big = [s for s in cf.symbols if s["name"] == "Big"][0]
        e = codemap.cpp_entry(cf, big)
        lines = codemap.explore_fit(e, 400)
        self.assertEqual(lines[:5], ["big.h:1-33 class Big", " 1\tclass Big {",
                                     "  3-12 method Big::f0", "  13-22 method Big::f1",
                                     "  23-32 method Big::f2"])

    def test_explore_fallback_range(self):
        text = ("int ok(void) { return 1; }\nvoid broken(int x)\n{\n    if (x) {\n"
                "        x++;\n}\n\nint later(void) { return 2; }\n")
        cf = codemap.CppFile("b.c", text)
        self.assertFalse(cf.clean)
        heads = [codemap.explore_header(codemap.cpp_entry(cf, s)) for s in cf.symbols]
        self.assertEqual(heads, [
            "b.c:1-1 function ok (end approximate: braces do not balance in this file; scan "
            "stopped at line 3)",
            "b.c:2-8 function broken (end approximate: braces do not balance in this file; "
            "scan stopped at line 3)"])

    def test_ifdef_branches_first_branch(self):
        text = ("#ifdef A\nvoid f(int x) {\n#else\nvoid f(long x) {\n#endif\n    g();\n}\n"
                "void h(void) {}\n")
        cf = codemap.CppFile("b.c", text)
        self.assertTrue(cf.clean)
        self.assertEqual([(s["name"], s["start"], s["end"]) for s in cf.symbols],
                         [("f", 2, 7), ("h", 8, 8)])

    def test_calls_reasons(self):
        out = self.run_ok("calls", "Fire")
        self.assertIn("definitions:\n  Source/MyGame/Private/MyActor.cpp:10 AMyActor::Fire (C++ "
                      "method) [UFUNCTION BlueprintCallable] (declared "
                      "Source/MyGame/Public/MyActor.h:19)\n", out)
        self.assertIn("callers: not resolved for C/C++ (possible: lists its text occurrences)\n",
                      out)
        for line in ("MyActor.cpp:21 delegate binding (SetTimer)",
                     "MyActor.cpp:23 delegate binding by name (BindUFunction)",
                     "MyActor.cpp:29 call", "MyActor.cpp:13 string"):
            self.assertIn(line, out)
        text = [x for x in out.split("\n") if x.startswith("text: ")][0]
        for part in ("C/C++ not resolved: overloads, templates, macros, virtual dispatch, "
                     "function pointers and delegates",
                     "bound to a delegate or timer at 2 places (called through it)",
                     "UFUNCTION: may be called by reflection or from Blueprints (assets are not "
                     "read)", "; grep the rest"):
            self.assertIn(part, text)
        self.assertIn("\ncoverage: ", out)
        out = self.run_ok("calls", "HandleHit")
        self.assertIn("MyActor.cpp:19 delegate binding (AddDynamic)", out)
        out = self.run_ok("calls", "clib_close")
        self.assertIn("1 line in `#if 0` blocks, not listed", out)
        self.assertIn("clib/src/clib.c:8 string", out)
        out = self.run_ok("calls", "UToolLib::Help")
        self.assertIn("Plugins/MyTools/Source/MyTools/Private/ToolLib.cpp:3 UToolLib::Help (C++ "
                      "method) [UFUNCTION BlueprintPure]", out)
        self.assertIn("MyActor.cpp:24 qualified call", out)


GOLDEN = {  # a Python, JavaScript and TypeScript project; its output under 0.9.26
    "app/main.py": "from app import util\nfrom app.util import Helper\n\n\ndef run():\n"
                   "    return Helper().go(util.VALUE)\n",
    "app/util.py": "VALUE = 1\n\n\nclass Helper:\n    def go(self, x):\n        return x\n",
    "web/index.ts": "import { x } from './lib';\nexport function start(): number { return x; }\n",
    "web/lib.ts": "export const x = 1;\nexport class Box {}\n",
    "web/app.js": "const lib = require('./util');\nfunction boot() { return lib.y; }\n"
                  "module.exports = { boot };\n",
    "web/util.js": "exports.y = 2;\n",
    "tools/run.sh": "#!/bin/sh\necho hi\n",
    "tests/test_util.py": "from app.util import Helper\n\n\ndef test_go():\n"
                          "    assert Helper().go(1) == 1\n",
}
GOLDEN_SHA256 = "f1611c46ff58f81ddfe6dc531e534ba1bc8b63c3d2eb257858751f5f9247e647"


class IncludeRootsTest(unittest.TestCase):
    """A module's own folder, its parent and its `Build.cs` include paths are include roots;
    an include found under none of them that ends one tracked file's path is a possible
    importer, never an importer and never an engine header."""

    def setUp(self):
        tmp = portability.temp_dir()
        self.addCleanup(tmp.cleanup)
        self.root = tmp.name
        fx = "Plugins/Fx/Source/FxCore/"
        for rel, data in (
                ("Game.uproject", '{"FileVersion": 3}\n'),
                ("Source/Shooter/Shooter.Build.cs",
                 "public class Shooter : ModuleRules { public Shooter(ReadOnlyTargetRules T) : "
                 "base(T) {\n  PublicIncludePaths.AddRange(new string[] { \"Shooter\", "
                 "\"Shooter/Variant_Combat\" });\n  PrivateIncludePaths.Add("
                 "Path.Combine(ModuleDirectory, \"Variant_Combat\", \"Menu\"));\n"
                 "  PublicDependencyModuleNames.AddRange(new string[] { \"Core\" }); } }\n"),
                ("Source/Shooter/ShooterCharacter.h",
                 "#pragma once\nclass AShooterCharacter {};\n"),
                ("Source/Shooter/AI/ShooterAI.h",
                 "#pragma once\n#include \"ShooterCharacter.h\"\n"
                 "#include \"Shooter/ShooterCharacter.h\"\n#include \"CombatHUD.h\"\n"
                 "#include \"CombatGame.h\"\n#include \"MenuWidget.h\"\n"
                 "#include \"Fx/FxSpawner.h\"\n"),
                ("Source/Shooter/Variant_Combat/CombatGame.h", "#pragma once\nint Combat();\n"),
                ("Source/Shooter/Variant_Combat/UI/CombatHUD.h", "#pragma once\nint Hud();\n"),
                ("Source/Shooter/Variant_Combat/Menu/MenuWidget.h", "#pragma once\nint Menu();\n"),
                (fx + "FxCore.Build.cs", "public class FxCore : ModuleRules {}\n"),
                (fx + "Public/Fx/FxSpawner.h", "#pragma once\nint Spawn();\n"),
                (fx + "Private/FxSpawner.cpp",
                 "#include \"Fx/FxSpawner.h\"\n#include \"FxSpawner.h\"\n"
                 "int Spawn() { return 1; }\n"),
                ("test/gtest/gtest/gtest.h", "#pragma once\nint Gtest();\n"),
                ("test/format-test.cc", "#include \"gtest/gtest.h\"\n#include \"gtest.h\"\n"),
                ("test/other/gtest.h", "#pragma once\n")):
            write(self.root, rel, data)
        subprocess.run(["git", "init", "-q", self.root], check=True)
        subprocess.run(["git", "-C", self.root, "add", "-A"], check=True)

    def run_ok(self, *args):
        code, out = run(*args, "--root", self.root)
        self.assertEqual(code, 0, out)
        return out

    def test_module_roots_and_build_paths(self):
        out = self.run_ok("impact", "Source/Shooter/ShooterCharacter.h")
        self.assertIn("  imported by: Source/Shooter/AI/ShooterAI.h\n", out)
        for header in ("Source/Shooter/Variant_Combat/CombatGame.h",
                       "Source/Shooter/Variant_Combat/Menu/MenuWidget.h",
                       "Plugins/Fx/Source/FxCore/Public/Fx/FxSpawner.h"):
            out = self.run_ok("impact", header)
            self.assertIn("Source/Shooter/AI/ShooterAI.h", out.split("  imported by: ")[1])
            self.assertNotIn("possibly", out)

    def test_suffix_matches_are_possible_importers(self):
        out = self.run_ok("impact", "Source/Shooter/Variant_Combat/UI/CombatHUD.h")
        self.assertNotIn("  imported by:", out)
        self.assertIn("  not followed: possibly imported by Source/Shooter/AI/ShooterAI.h (", out)
        out = self.run_ok("query", "gtest/gtest.h")
        self.assertIn("  test/gtest/gtest/gtest.h (imported by 0 local files)\n"
                      "    possibly imported by test/format-test.cc (not followed: ", out)
        out = self.run_ok("query", "other/gtest.h")  # `gtest.h` ends two paths: no guess
        self.assertNotIn("possibly", out)
        out = self.run_ok("impact", "Plugins/Fx/Source/FxCore/Public/Fx/FxSpawner.h")
        self.assertIn("  imported by: Plugins/Fx/Source/FxCore/Private/FxSpawner.cpp, "
                      "Source/Shooter/AI/ShooterAI.h\n", out)  # also a resolved importer: once
        self.assertNotIn("possibly", out)
        self.run_ok("build")
        with open(os.path.join(self.root, "docs", "code-map.md"), encoding="utf-8") as fh:
            page = fh.read()
        self.assertIn("0 `\"...\"` includes not found among the tracked files (engine, system or "
                      "generated headers)", page)
        self.assertIn(" 4 more name a path that ends a tracked file's path", page)


class ResolveTest(unittest.TestCase):
    def test_nearest_root_wins_and_ties_stay_unresolved(self):
        files = ["libs/alpha/include/util.h", "libs/alpha/src/util.cpp",
                 "libs/beta/include/util.h", "libs/beta/src/util.cpp", "libs/beta/src/main.cpp",
                 "app/main.cpp", "Phys/Phys.h", "Phys/Core/Core.h", "Samples/demo.cpp"]
        incs = codemap.CppIncludes(files)
        self.assertEqual(incs.resolve("libs/beta/src/util.cpp", '"', "util.h"),
                         "libs/beta/include/util.h")
        self.assertEqual(incs.resolve("libs/beta/src/main.cpp", "<", "util.h"),
                         "libs/beta/include/util.h")
        self.assertEqual(incs.resolve("libs/alpha/src/util.cpp", '"', "util.h"),
                         "libs/alpha/include/util.h")
        self.assertIsNone(incs.resolve("app/main.cpp", '"', "util.h"))  # equally near: none
        # `<Lib/x.h>` from the repository root: `Phys/` is a top-level folder with headers
        self.assertEqual(incs.resolve("Samples/demo.cpp", "<", "Phys/Core/Core.h"),
                         "Phys/Core/Core.h")
        self.assertIsNone(incs.resolve("Samples/demo.cpp", "<", "Core.h"))


class VendoredTest(unittest.TestCase):
    """Vendored folders (`third_party`, `ThirdParty`, ...) are not scanned; the map page says
    how many tracked files that leaves out, and where."""

    def build(self, files):
        tmp = portability.temp_dir()
        self.addCleanup(tmp.cleanup)
        for rel, data in files:
            write(tmp.name, rel, data)
        subprocess.run(["git", "init", "-q", tmp.name], check=True)
        subprocess.run(["git", "-C", tmp.name, "add", "-A"], check=True)
        code, out = run("build", "--root", tmp.name)
        self.assertEqual(code, 0, out)
        with open(os.path.join(tmp.name, "docs", "code-map.md"), encoding="utf-8") as fh:
            return fh.read()

    def test_exact_names_only(self):
        for path in ("thirdparty/a.c", "src/ThirdParty/a.h", "3rdparty/x/a.c",
                     "third_party/a.c"):
            self.assertTrue(codemap.skipped(path, "docs/code-map.md"), path)
        for path in ("THIRDPARTY/a.c", "Third_Party/a.c", "thirdparty.c", "src/3rdParty/a.c"):
            self.assertFalse(codemap.skipped(path, "docs/code-map.md"), path)

    def test_unreal_page_line(self):
        page = self.build((
            ("Game.uproject", "{}\n"),
            ("Source/Game/Game.Build.cs", "public class Game : ModuleRules {}\n"),
            ("Source/Game/Game.cpp", '#include "zlib.h"\nint Run() { return 0; }\n'),
            ("Source/ThirdParty/zlib/zlib.Build.cs", "public class zlib : ModuleRules {}\n"),
            ("Source/ThirdParty/zlib/include/zlib.h", "int inflate();\n"),
            ("thirdparty/a/x.c", "int x;\n"), ("3rdparty/y.c", "int y;\n"),
            ("lib/vendor/z.c", "int z;\n")))
        self.assertIn("(0 tracked files).\nNot scanned: vendored folders (5 tracked files: "
                      "`3rdparty/`, `Source/ThirdParty/`, `lib/vendor/`, `thirdparty/`).\n"
                      "Binary assets", page)
        self.assertNotIn("`zlib`", page)  # its module is not listed
        self.assertIn("1 `\"...\"` includes not found among the tracked files", page)

    def test_other_repo_page_line(self):
        page = self.build((("app/main.py", "import os\n"),
                           ("vendor/lib/x.py", "def x():\n    pass\n")))
        self.assertIn("- `app/main.py`\n\nNot scanned: vendored folders (1 tracked files: "
                      "`vendor/`).\n\n## `app`", page)
        page = self.build((("app/main.py", "import os\n"),))
        self.assertNotIn("vendored", page)


class ScaleTest(unittest.TestCase):
    """Linking declarations and definitions and resolving includes stay about linear."""

    @staticmethod
    def project(n, modules):
        files = {}
        for i in range(n):
            m = "Source/M%d" % (i % modules)
            files["%s/M%d.Build.cs" % (m, i % modules)] = ""
            files["%s/Public/A%d.h" % (m, i)] = (
                "#pragma once\n#include \"CoreMinimal.h\"\n#include \"A%d.h\"\n"
                "UCLASS()\nclass A%d : public AActor {\n  GENERATED_BODY()\npublic:\n"
                "  virtual void BeginPlay() override;\n  virtual void Tick(float D) override;\n"
                "  UFUNCTION(Server, Reliable)\n  void Fire(int32 N);\n};\n"
                % ((i + 1) % n, i))
            files["%s/Private/A%d.cpp" % (m, i)] = (
                "#include \"A%d.h\"\n#include \"A%d.h\"\n#include <vector>\n"
                "void A%d::BeginPlay() { Super::BeginPlay(); }\n"
                "void A%d::Tick(float D) { Super::Tick(D); }\n"
                "void A%d::Fire_Implementation(int32 N) {}\n" % (i, (i * 7) % n, i, i, i))
        return files

    def timed(self, n, modules):
        files = self.project(n, modules)
        t = time.perf_counter()
        incs = codemap.CppIncludes(sorted(files))
        cfiles = {p: codemap.CppFile(p, text) for p, text in files.items()
                  if p.endswith((".h", ".cpp"))}
        resolved = sum(incs.resolve(p, kind, spec) is not None
                       for p, cf in cfiles.items() for _, kind, spec in cf.includes)
        codemap.cpp_link(cfiles)
        elapsed = time.perf_counter() - t
        self.assertEqual(resolved, 3 * n)  # not `CoreMinimal.h`, `<vector>`
        fire = [s for s in cfiles["Source/M0/Private/A0.cpp"].symbols if s["name"] ==
                "Fire_Implementation"][0]
        self.assertEqual([d["path"] for d in fire["declared"]], ["Source/M0/Public/A0.h"])
        return elapsed

    def ratio(self, run, small, large):
        """The fastest of three runs of `run(*small)` and of `run(*large)`, compared."""
        small, large = (min(run(*args) for _ in range(3)) for args in (small, large))
        self.assertLess(large, 30.0)
        self.assertLess(large / max(small, 1e-3), 4 * 3, (small, large))

    def test_classes_scale_linearly(self):
        self.ratio(self.timed, (250, 10), (1000, 10))

    def test_many_modules_include_heavy(self):
        self.ratio(self.timed, (300, 30), (1200, 120))

    def relative(self, modules, wide):
        """`"../Public/Base.h"` from every module, and (`wide`) one deleted header asked for
        from every file, as `changed` does after a diff that deletes it."""
        files = []
        for m in range(modules):
            b = "Source/M%d" % m
            files += [b + "/M%d.Build.cs" % m, b + "/Public/Base%d.h" % m]
            files += ["%s/Private/Sub/A%d_%d.cpp" % (b, m, j) for j in range(10)]
        t = time.perf_counter()
        incs = codemap.CppIncludes(sorted(files))
        if wide:
            incs.deleted(["Source/M0/Public/Gone.h"])
        hits = 0
        for f in files:
            if f.endswith(".cpp"):
                m = int(f.split("/")[1][1:])
                spec = "../Public/Base%d.h" % ((m + 1) % modules)
                hits += incs.resolve(f, '"', spec) is not None
                if wide:
                    hits += incs.resolve(f, '"', "Gone.h", True) == "Source/M0/Public/Gone.h"
        elapsed = time.perf_counter() - t
        self.assertEqual(hits, 10 * modules * (2 if wide else 1))
        return elapsed

    def test_parent_relative_includes_many_modules(self):
        self.ratio(self.relative, (100, False), (400, False))

    def test_deleted_header_many_modules(self):
        self.ratio(self.relative, (100, True), (400, True))


class UnchangedTest(unittest.TestCase):
    def test_python_js_ts_output_as_before(self):
        """build, query, calls, explore and impact print what 0.9.26 printed, byte for byte."""
        import hashlib
        tmp = portability.temp_dir()
        self.addCleanup(tmp.cleanup)
        for rel, data in GOLDEN.items():
            write(tmp.name, rel, data)
        subprocess.run(["git", "init", "-q", tmp.name], check=True)
        subprocess.run(["git", "-C", tmp.name, "add", "-A"], check=True)
        out = []
        for argv in (["build"], ["query", "Helper"], ["query", "lib"], ["calls", "go"],
                     ["explore", "Helper"], ["explore", "start"], ["impact", "app/util.py"],
                     ["impact", "web/lib.ts"]):
            code, text = run(*argv, "--root", tmp.name)
            out.append("== %s %s\n%s" % (" ".join(argv), code, text))
        with open(os.path.join(tmp.name, "docs", "code-map.md"), encoding="utf-8",
                  newline="") as fh:
            out.append(fh.read())
        got = "".join(out)
        self.assertNotIn("C/C++", got)
        self.assertEqual(hashlib.sha256(got.encode("utf-8")).hexdigest(), GOLDEN_SHA256, got)


class WarningTest(unittest.TestCase):
    def test_python_syntax_warnings_silenced(self):
        tmp = portability.temp_dir()
        self.addCleanup(tmp.cleanup)
        write(tmp.name, "pkg/esc.py", 'import re\n\n\ndef digits(s):\n'
                                      '    return re.findall("\\d+", s) is not 1\n')
        subprocess.run(["git", "init", "-q", tmp.name], check=True)
        subprocess.run(["git", "-C", tmp.name, "add", "-A"], check=True)
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "codemap.py")
        for action in (["calls", "digits"], ["explore", "digits"]):
            p = subprocess.run([sys.executable, "-W", "default", script] + action
                               + ["--root", tmp.name], capture_output=True, text=True)
            self.assertEqual((p.returncode, p.stderr), (0, ""), action)
            self.assertIn("pkg/esc.py:4", p.stdout)


class PipeTest(unittest.TestCase):
    def test_closed_pipe_exits_quietly(self):
        tmp = portability.temp_dir()
        self.addCleanup(tmp.cleanup)
        make_fixture(tmp.name)
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "codemap.py")
        for action in (["calls", "Fire"], ["query", "AMyActor"], ["explore", "AMyActor"],
                       ["build"]):
            p = subprocess.Popen([sys.executable, script] + action + ["--root", tmp.name],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p.stdout.close()  # the reader is gone before anything is written
            err = p.stderr.read()
            p.stderr.close()
            self.assertEqual((p.wait(), err), (0, b""), action)


if __name__ == "__main__":
    unittest.main()
