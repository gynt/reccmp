# Recommendations

The following is a list of recommendations and best practices we have established at the [LEGO Island Decompilation project](https://github.com/isledecomp/isle). They do not affect the output of `reccmp`, so it is up to you if you want to use them.

## Class/struct size annotation and assertion

Once we have a reasonable guess for the size of a class or struct, we add it in a comment like so:

```c++
// SIZE 0x1c
class MxCriticalSection {
public:
    MxCriticalSection();
    ~MxCriticalSection();
    static void SetDoMutex();
    // ...
}
```

Furthermore, we use a compile-time assertion to verify that the recompiled size is correct (see also [this file](https://github.com/isledecomp/isle/blob/82453f62d84f979f8a6fc7b46e21b61cb835d2f1/util/decomp.h)):

```c++
#define DECOMP_STATIC_ASSERT(V)       \
    namespace                         \
    {                                 \
    typedef int foo[(V) ? 1 : -1];    \
    }
#define DECOMP_SIZE_ASSERT(T, S) DECOMP_STATIC_ASSERT(sizeof(T) == S)
```

Then we add `DECOMP_SIZE_ASSERT(MxCriticalSection, 0x1c)` to the respective `.cpp` file (if the class has no dedicated `.cpp` file, we use any appropriate `.cpp` file where the class is used).

## Member variables

We annotate member variables with their relative offsets.

```c++
class MxDSObject : public MxCore {
private:
    MxU32 m_sizeOnDisk;   // 0x08
    MxU16 m_type;         // 0x0c
    char* m_sourceName;   // 0x10
    undefined4 m_unk0x14; // 0x14
    // ...
}
```

## VTable members

In addition to the `VTABLE` annotation (which is relevant to `reccmp`), we also add comments to indicate the relative offset of each function:

```c++
// VTABLE: LEGO1 0x100dc900
class MxEventManager : public MxMediaManager {
public:
    MxEventManager();
    virtual ~MxEventManager() override;

    virtual void Destroy() override;                                     // vtable+0x18
    virtual MxResult Create(MxU32 p_frequencyMS, MxBool p_createThread); // vtable+0x28
    // ...
}
```

## Aliases for unknown scalar types

In order to distinguish known from unknown types, we have added the following typedefs:

```c++
typedef unsigned char undefined;
typedef unsigned short undefined2;
typedef unsigned int undefined4;
```

Note that the behaviour of signed and unsigned integers can be different even when no arithmetic is involved. If changing e.g. from `undefined4` to `int` improves the match, this is a strong indicator that the original variable was signed as well.

## Calls routed through a wrapper function

Some projects cannot emit a direct call to an original function and instead
generate a wrapper (often a template instantiation, e.g. a `FunctionResolver`)
that performs the call. The recomp assembly then reads

```
0x4b21db : -call <OFFSET12>
         : +call FunctionResolver::Resolver<void (__thiscall A::B::*)(int),0,4657152,&A::B::f,0>::GameFunction<...>::CallHelper<void,void>::call (FUNCTION)
```

Every such call counts as a mismatch, so an otherwise perfect function can
never reach 100%. `reccmp-reccmp` offers two options for this situation:

* `--resolve-wrapped-calls` uses the fact that the original address of the
  called function appears inside the wrapper's name, because that is how the
  wrapper is parameterized (`4657152` == `0x471000` above). If that number is
  the target address of the call on the original side, the two instructions
  describe the same call and the recomp instruction is rewritten to the text
  used by the original one. Calls that go somewhere else are left alone, so
  genuinely wrong calls are still reported. Both decimal and hexadecimal
  (`0x...`) numbers are recognized, and numbers below `0x1000` are ignored so
  that small template parameters are not mistaken for an address.
* `--ignore-call-targets` is the blunt alternative: the target of every call is
  replaced by a `<CALL>` placeholder in both binaries, so call targets never
  contribute to the difference. This also hides real call mismatches, so prefer
  `--resolve-wrapped-calls` where it works. If both options are given,
  `--ignore-call-targets` wins.

Neither option is enabled by default.
