cmake_minimum_required(VERSION 3.13)
include(pico_sdk_import.cmake)
project(hqc_encaps_pico C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
pico_sdk_init()

# The HQC-128 sources are the vendored PQClean copy of the ArduPilot fork
# (https://github.com/cdcp2/ardupilot_post_quantum_kem): <clone>/libraries/AP_KEM/vendor/pqclean,
# checked out at cd7be51~1 (unmodified reference) or b402392 (hand-optimized variant, finding F6).
# Pass it as -DPQCLEAN_VENDOR=... or export PQCLEAN_VENDOR in the environment.
if(NOT PQCLEAN_VENDOR)
    set(PQCLEAN_VENDOR "$ENV{PQCLEAN_VENDOR}")
endif()
if(NOT PQCLEAN_VENDOR)
    message(FATAL_ERROR "Set PQCLEAN_VENDOR to <clone of cdcp2/ardupilot_post_quantum_kem>/libraries/AP_KEM/vendor/pqclean")
endif()
set(HQC128_CLEAN "${PQCLEAN_VENDOR}/crypto_kem/hqc-128/clean")

# main.c times 500 encapsulations; main_selfcheck.c also decapsulates and counts failures
# (-DHQC_MAIN=main_selfcheck.c). -DARBOL=<commit> writes the tree's commit into the serial log.
if(NOT HQC_MAIN)
    set(HQC_MAIN main.c)
endif()

set(HQC_SRCS
    ${HQC_MAIN}
    randombytes_pico.c
    "${PQCLEAN_VENDOR}/common/fips202.c"
    "${HQC128_CLEAN}/code.c"
    "${HQC128_CLEAN}/fft.c"
    "${HQC128_CLEAN}/gf2x.c"
    "${HQC128_CLEAN}/gf.c"
    "${HQC128_CLEAN}/hqc.c"
    "${HQC128_CLEAN}/kem.c"
    "${HQC128_CLEAN}/parsing.c"
    "${HQC128_CLEAN}/reed_muller.c"
    "${HQC128_CLEAN}/reed_solomon.c"
    "${HQC128_CLEAN}/shake_ds.c"
    "${HQC128_CLEAN}/shake_prng.c"
    "${HQC128_CLEAN}/vector.c"
)
# The variant (from cd7be51 on) adds two files that the reference tree does not have.
foreach(extra gf2x_sparse.c vector_sparse.c)
    if(EXISTS "${HQC128_CLEAN}/${extra}")
        list(APPEND HQC_SRCS "${HQC128_CLEAN}/${extra}")
    endif()
endforeach()

add_executable(hqc_encaps_pico ${HQC_SRCS})
target_include_directories(hqc_encaps_pico PRIVATE "${PQCLEAN_VENDOR}/common" "${HQC128_CLEAN}")
if(ARBOL)
    target_compile_definitions(hqc_encaps_pico PRIVATE ARBOL="${ARBOL}")
endif()
target_link_libraries(hqc_encaps_pico pico_stdlib pico_rand)
pico_enable_stdio_usb(hqc_encaps_pico 1)
pico_enable_stdio_uart(hqc_encaps_pico 0)
pico_add_extra_outputs(hqc_encaps_pico)
