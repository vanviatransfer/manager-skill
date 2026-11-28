# C, C++ and Unreal Engine

Read by the code-map skill when the repository holds C or C++ code (an Unreal Engine project
too). What the map, `query`, `impact`, `explore` and `calls` see in it, and what they miss.

Files: `.c` (C), `.h` (C/C++), `.cpp`, `.cc`, `.cxx`, `.hpp`, `.hh`, `.hxx`, `.inl` (C++).
Everything comes from line patterns over the text, with no compiler and no preprocessor:
comments, string and character literals (raw strings too) are blanked first, so braces and names
inside them count for nothing.

## Symbols

Recognised at file and namespace level, kind-tagged (`query` prints the kind):
- functions: definitions, and declarations (`function declaration`, mostly in headers); a
  definition and its declarations (the same qualified name, the same file first, then the same
  number of parameters) are one symbol: `explore` and `calls` print the definition with
  `(declared <file>:<line>)`;
- `class`, `struct`, `union`, `enum`, `enum class`, `namespace` (nested, and `namespace a::b`),
  `typedef` (also `typedef struct {...} Name;` and function pointer types), `using X = ...`;
- `#define` macros, object-like and function-like (not include guards);
- class members, for `explore`'s member lists: methods (declared or defined in the body),
  constructors, destructors, operators, and Unreal `UPROPERTY` fields;
- out-of-class definitions `Ret Class::Method(...)`: a `method` of `Class` when that class is
  known, with the declaration's location;
- prefixes skipped before a declaration: `template <...>`, `inline`, `static`, `constexpr`,
  `virtual`, `explicit`, `extern "C"`, `[[attributes]]`, `__declspec(...)`, `__attribute__((...))`,
  and a line holding only an upper-case macro call.

Multi-line signatures are read up to 40 lines; a longer head is not classified. `#if 0` blocks
are skipped. Other `#if`/`#ifdef` branches are all read; when that leaves the braces unbalanced
(each branch opening its own `{`), only the first branch of each is read.

The map page lists namespace-level symbols per file (one per name, a definition before a
declaration; macros, then namespaces last) and the Unreal members that Blueprints may use.
`changed` compares the text between those symbols, as for other languages (approximate).

## Unreal Engine

- Reflection macros before a declaration are its tag, on the page and in `query`, `explore` and
  `calls`: `UCLASS(...)`, `USTRUCT(...)`, `UENUM(...)`, `UINTERFACE(...)`, `UFUNCTION(...)`,
  `UPROPERTY(...)`, `UDELEGATE(...)`, shortened to the macro and its first specifiers
  (`[UFUNCTION BlueprintCallable]`). A definition in a `.cpp` takes its declaration's tag.
- `class MYGAME_API AMyActor : public AActor`: any `[A-Z0-9_]+_API` macro is skipped;
  `GENERATED_BODY()` and `GENERATED_UCLASS_BODY()` too.
- `DECLARE_*DELEGATE*` and `DECLARE_*EVENT*` (dynamic, multicast and sparse): the delegate type
  is a symbol (`FOnHit`, kind `dynamic multicast delegate`).
- Log categories: `DECLARE_LOG_CATEGORY_EXTERN(LogMyGame, ...)` and `DEFINE_LOG_CATEGORY(...)`.
- On the map page, members tagged `UFUNCTION`, and `UPROPERTY` with a `Blueprint` specifier,
  are listed after their class (`AMyActor::Fire [UFUNCTION BlueprintCallable]`).
- The map page's **Unreal Engine** section names the `.uproject` and `.uplugin` files and lists
  each module (a folder holding `<Name>.Build.cs`) with its `PublicDependencyModuleNames` and
  `PrivateDependencyModuleNames` as written: conditions (`if (Target.Platform ...)`) are not
  evaluated and names built in code are not seen.
- With a `.uproject` tracked, `Binaries/`, `Intermediate/`, `Saved/`, `DerivedDataCache/` and
  `.vs/` in its folder and in every `.uplugin` folder are not scanned (the page counts them).
- `.uasset` and `.umap` files are never read: Blueprint and level references to C++ are not
  seen, so a `UFUNCTION` or `UPROPERTY` with no text caller may still be used.

## Includes

`#include "..."` is resolved to a tracked file: relative to the including file, then the include
roots: in an Unreal project its own module's `Public/`, `Private/` and `Classes/`, then every other
module's; then the repository root and every folder named `include`, `inc`, `src` or `Source`
(shallowest first); last, a single tracked file matching ignoring case. Resolved includes are
imports: `query` paths, the page's "Most imported", `impact` and `changed` use them.

Counted, never followed, and named on the page's **C and C++ includes** section: `<...>`
includes, `"..."` includes not found among the tracked files (engine headers such as
`CoreMinimal.h`, system and generated headers, `*.generated.h`), and computed ones
(`#include MACRO`). `query` adds `<k> of its includes not followed` to a path. Compiler include
paths (`-I`, CMake, `.vcxproj`) are not read, so a header found only through them is unresolved.

## `explore` and `calls`

- `explore`: a definition's range comes from brace matching, exact when the file's braces
  balance; otherwise the end is approximate (`end approximate: braces do not balance in this
  file`), as for other languages. A class too big to show lists its members with ranges (and
  where an out-of-class definition is). A name matching a class and its constructor shows the
  class; `X::X` names the constructor. `callers:` says they are not resolved and points to
  `calls`.
- `calls` resolves nothing for C/C++. It prints the definitions, then every whole-word
  occurrence under `possible:`, kind-tagged by its text (`call`, `member call`, `qualified call`,
  `reference`, `macro`, `string`, `other definition`, `delegate binding (AddDynamic)`, `delegate
  binding by name (BindUFunction)`), and the `text:` line names why it is incomplete: overloads,
  templates, macros, virtual dispatch, function pointers and delegates; the count bound to a
  delegate or timer; a `UFUNCTION` may be called by reflection or from Blueprints; lines in `#if
  0` blocks are not listed. Code outside the repository (the engine, other projects) is never
  seen. Grep the rest.

## Known misses

- Macros are not expanded: a declaration produced by a macro (`DECLARE_CLASS(...)`, X-macros) is
  not seen, and a macro that opens or closes a brace unbalances the file (approximate ranges).
- A function whose body never closes in the text keeps an unknown end; definitions after it, inside
  the unclosed brace, are not seen.
- Template specialisations and overloads with the same name are separate entries; which one a
  call uses is not known.
- Variables and fields are not symbols (except Unreal `UPROPERTY` fields and log categories).
- A K&R-style C definition (`int f(a, b) int a; int b; {...}`) is not seen.
