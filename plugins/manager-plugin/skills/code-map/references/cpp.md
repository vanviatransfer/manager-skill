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
  definition and its declarations are one symbol: `explore` and `calls` print the definition
  with `(declared <file>:<line>)`. A declaration pairs when its qualified name ends the
  definition's (a definition is never less qualified: a top-level `f` is not `a::f`; under
  `using namespace a;` an unqualified definition stays unpaired), the nearest scope first, then
  the same number of parameters (an overload with another count is not taken unless it is the
  only candidate), then the same file; a `friend` function defined in a class body (a hidden
  friend, `friend bool operator==(...) {...}`, also after `inline`, `constexpr`, `consteval` or
  `static` in any order) is a function of the enclosing namespace, not a member, and pairs
  with a namespace-level declaration;
- `class`, `struct`, `union`, `enum`, `enum class`, `namespace` (nested, and `namespace a::b`),
  `typedef` (also `typedef struct {...} Name;` and function pointer types), `using X = ...`;
- `#define` macros, object-like and function-like (not include guards);
- class members, for `explore`'s member lists: methods (declared or defined in the body),
  constructors, destructors, operators (conversion operators too), and Unreal `UPROPERTY`
  fields; `X() = default;` and `X(const X&) = delete;` are `defaulted` / `deleted` members,
  never paired with a definition elsewhere;
- signatures: trailing return types (`auto f() -> std::string`), `decltype(auto)`, nested
  `noexcept(noexcept(...))`, a parenthesised name (`int (max)(int, int)`), a function returning a
  function pointer (`void (*get_cb(void))(int)`), and `>` inside a template argument's
  parentheses (`enable_if_t<(sizeof(T) > 4)>`), and tail words after the parameter list:
  `const`, `noexcept(...)`, `override`, upper-case macros (`ENGINE_DEPRECATED(...)`) and
  underscore-led ones (`__THROW`, `__wur`, `_NOEXCEPT`, `__nonnull((1))`,
  `__attribute__((...))`, SAL annotations such as `_Requires_lock_held_(cs)`), asm labels
  (`__asm__("x")`, `asm("x")`); a lower-case macro without a leading underscore (`const_fn`) leaves
  the function unclassified;
- out-of-class definitions `Ret Class::Method(...)`: a `method` of `Class` when that class is
  known, with the declaration's location;
- prefixes skipped before a declaration: `template <...>`, a C++20 `requires` clause (names,
  `<...>` arguments and parenthesised expressions joined by `&&` / `||`), `inline`, `static`,
  `constexpr`, `virtual`, `explicit`, `extern "C"`, `[[attributes]]`, `__declspec(...)`,
  `__attribute__((...))`, an upper-case macro before a keyword or type (`MYLIB_EXPORT
  template <...> class X`, `class MYLIB_EXPORT X`, `MYLIB_PUBLIC(int) f()`), an upper-case
  macro call alone on its line or lines (`DISABLE_WARNINGS_PUSH_(...)`), and an upper-case macro
  call between the return type and the name (`static void PRINTF_FUNC(7, 8) log_msg(...)`: the
  name is `log_msg`; not when what follows is `__declspec(...)`, `noexcept(...)` or another
  upper-case macro, which are tail words).

A brace block the patterns cannot classify is skipped on its own: the next declaration starts
after it, so one miss does not hide the definitions that follow (only `= {...}` and `x{...}`
initializers continue the declaration they belong to; an `=` inside parentheses or template
arguments, such as a default argument, is not an initializer).

Multi-line signatures are read up to 40 lines; a longer head is not classified. A directive
goes on while its lines end with `\`, also inside a comment (`/* a \` in a multi-line
`#define`). `#if 0` blocks are skipped. Other `#if`/`#ifdef` branches are all read; when that
leaves the braces unbalanced (each branch opening its own `{`), only the first branch of each
is read, unless that scan stops earlier than the first. A scan that stops (a `{` or `(` in a
declaration never closed) reads nothing after that line: the page marks the file `(scan stopped
at line N: a bracket never closes)` and `explore` adds `scan stopped at line N` to its
approximate-range note. When the name appears in such a file after the line where its scan
stopped, `explore` (on its no-match line) and `calls` (a line of its own) say `scan stopped in
<file> (line N), before a line naming it`.

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
  is a symbol (`FOnHit`, kind `dynamic multicast delegate`; for `*_RetVal_*` and events, the
  second argument).
- RPCs and native events: a definition `X_Implementation` or `X_Validate` with no declaration of
  its own pairs with the `UFUNCTION` declaration `X` (`Server`, `Client`, `NetMulticast`,
  `BlueprintNativeEvent`, `WithValidation`), so `explore X` and `calls X` show them, with the
  tag and the declaration's location; the declaration says `(bodies: X_Implementation,
  X_Validate)`.
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
- `Source/ThirdParty/` and other vendored folders are not scanned (next section): their
  `Build.cs` modules drop off the Modules list, and includes into them count as not found.

## Vendored folders

Folders named exactly `third_party`, `thirdparty`, `ThirdParty`, `3rdparty`, `vendor` or
`node_modules` (case as written: `THIRDPARTY` and `3rdParty` are read), at any depth, are not
scanned in any language. The map page says so on one line, in the Unreal Engine section when
there is one, else after the other sections: `Not scanned: vendored folders (<n> tracked files:
<the outermost such folders, the first 10>)`. One inside another skipped folder (`dist/vendor/`,
`.venv/.../vendor/`) is neither listed nor counted. Outside git the files on disk under them are
counted (never read). A repository without them gets no such line.

## Includes

`#include "..."` is resolved to a tracked file: relative to the including file, then the include
roots: in an Unreal project its own module's folder, `Public/`, `Private/`, `Classes/`, the
module's parent folder, and the folders its `Build.cs` adds with `PublicIncludePaths` /
`PrivateIncludePaths` (string literals, each relative to the module folder and to its parent,
and `Path.Combine(ModuleDirectory, "X")`; other computed paths are not read), then every other
module's and the repository root and every folder named `include`, `inc`, `src` or `Source`:
of the files found under these, the one whose root is nearest the including file (fewest folder
steps, so `libs/beta/src/x.cpp` gets `libs/beta/include/util.h`, not alpha's); two different
files equally near leave the include unresolved. Last, a single tracked file matching ignoring
case. `#include <...>` is followed only under those roots other than the repository root
(`<fmt/core.h>` to `include/fmt/core.h`; a project header of the same name as a system one,
such as a tracked `include/string.h`, is then taken for `<string.h>`); the repository root
counts for it when the path's first folder is a top-level folder holding headers
(`<Phys/Phys.h>` to `Phys/Phys.h`). Each folder, form and path is resolved once per run.
Resolved includes are imports: `query` paths, the page's "Most imported", `impact` and
`changed` use them.

Counted, never followed, and named on the page's **C and C++ includes** section: other `<...>`
includes, `"..."` includes not found among the tracked files (engine headers such as
`CoreMinimal.h`, system and generated headers, `*.generated.h`), and computed ones
(`#include MACRO`). `query` adds `<k> of its includes not followed` to a path. Compiler include
paths (`-I`, CMake, `.vcxproj`) are not read, so a header found only through them is unresolved.
An unresolved include (either form) whose path ends a tracked file's path (whole folder names:
`"gtest/gtest.h"` ends `test/gtest/gtest/gtest.h`) is counted apart on the page, not as an
engine or system header; when only one tracked file matches, `impact` on it says `not followed:
possibly imported by <files>` and `query` lists them as `possibly imported by`, never as
importers (the count `imported by N` leaves them out). When several files match, none is named.

## `explore` and `calls`

- `explore`: a definition's range comes from brace matching, exact when the file's braces
  balance; otherwise the end is approximate (`end approximate: braces do not balance in this
  file`), as for other languages. A class too big to show lists its members with ranges (and
  where an out-of-class definition is). A name matching a class and its constructor shows the
  class; `X::X` names the constructor; destructors and operators are named as written
  (`~X`, `X::~X`, `operator==`, `X::operator bool`; spaces after `~` or `operator` are
  dropped, or kept as one before a word). `callers:` says they are not resolved and points to
  `calls`; a suggested name with characters other than letters, digits, `_`, `.` and `:` is
  quoted for the shell, and its grep matches fixed text (`run calls 'operator bool'`, `grep -n
  -F -w '~X'`).
- `calls` resolves nothing for C/C++. It prints the definitions, then every whole-word
  occurrence under `possible:`, kind-tagged by its text (`call`, `member call`, `qualified call`,
  `reference`, `macro`, `string`, `other definition`, `delegate binding (AddDynamic)`, `delegate
  binding by name (BindUFunction)`; an operator's name is not matched where the next character
  continues the operator: `operator=` is not found in `operator==`, nor `operator<` in
  `operator<<`), and the `text:` line names why it is incomplete: overloads,
  templates, macros, virtual dispatch, function pointers and delegates; the count bound to a
  delegate or timer; a `UFUNCTION` may be called by reflection or from Blueprints; lines in `#if
  0` blocks are not listed; for an operator, a destructor or a constructor, that its implicit
  calls (`a == b`, scope exit, `delete`, a declaration) are not seen, also on `possible: none
  found (...)`. Occurrences that are not calls count as `named without a call at <k> places`.
  Code outside the repository (the engine, other projects) is never seen. Grep the rest. For a
  name defined only in C/C++, the `text:` line counts occurrences in files neither Python nor
  C/C++ as `in other files`, and the `coverage:` line describes C/C++ (nothing resolved)
  instead of Python's static calls.

## Known misses

- Speed: C/C++ files are parsed on every action, about 6 to 8 MB of source a second on one
  core; a repository with 150 MB of C/C++ takes about 25 s per action, and every action rescans
  (nothing is cached). The git pre-commit hook runs a full `build` on most commits that touch
  source files, and the Claude Code commit check runs a full `check`: on a large repository,
  time one `build` before offering the hook.
- Macros are not expanded: a declaration produced by a macro (`DECLARE_CLASS(...)`, X-macros) is
  not seen, and a macro that opens or closes a brace unbalances the file (approximate ranges).
- A function whose body never closes in the text keeps an unknown end; definitions after it, inside
  the unclosed brace, are not seen.
- Template specialisations and overloads with the same name are separate entries; which one a
  call uses is not known.
- Variables and fields are not symbols (except Unreal `UPROPERTY` fields and log categories).
- A K&R-style C definition (`int f(a, b) int a; int b; {...}`) is not seen.
- A `{` in a trailing return type (`-> decltype(f(T{}))`) ends the signature early: that
  function is unclassified (skipped, the next one still seen).
- Classes, structs and functions defined inside a function body are not symbols.
- An RPC body pairs by name only; overloads of `X` are not told apart.
- `possibly imported by` is a guess from the path alone: the include may name a header of the
  same path outside the repository or one chosen by an include path not read.
