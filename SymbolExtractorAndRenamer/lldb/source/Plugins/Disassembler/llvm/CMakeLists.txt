add_lldb_library(lldbPluginDisassemblerLLVM PLUGIN
  DisassemblerLLVMC.cpp

  LINK_LIBS
    lldbCore
    lldbSymbol
    lldbTarget
  LINK_COMPONENTS
    ${LLVM_TARGETS_TO_BUILD}
    MC
    Support
  )
