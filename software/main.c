
#include <io.h>
#include <system.h>
#include <stdint.h>


// Koristimo imena iz system.h fajla
#define WRAPPER_BASE   SYSTOLIC_ST_WRAPPER_1_BASE
#define FIFO_A_BASE    FIFO_0_BASE
#define FIFO_B_BASE    FIFO_1_BASE
#define FIFO_C_BASE    FIFO_2_BASE

// Adresa u RAM-u za softver upis
#define RESULT_PTR     0x0001FF00




 //* Pakuje dva 8-bitna podatka u jedan 32-bitni.
 //* Koristi se za slanje podataka u FIFO A i B.

uint32_t pack_to_32bit(int8_t low, int8_t high) {
    return ((uint32_t)((uint8_t)low)) | (((uint32_t)((uint8_t)high)) << 8);
}


 //* Izvlači 24-bitni rezultat iz 32-bitne pročitane iz FIFO C.
 //* Vrši sign-extension da bi broj bio validan u 32-bitnom C formatu.

int32_t extract_24bit(uint32_t val) {
    int32_t result = (int32_t)(val & 0xFFFFFF);
    if (result & 0x800000) { // Ako je 23. bit (znak) jednak 1
        result |= 0xFF000000;
    }
    return result;
}



int main() {
    // Definisanje ulaznih matrica 2x2
    int8_t matA[2][2] = {{1, 2}, {3, 4}};
    int8_t matB[2][2] = {{5, 6}, {7, 8}};
    
    // Pointer za markere merenja
    volatile uint32_t *marker = (uint32_t *)RESULT_PTR;

    // ==========================================
    // KORAK 1: POČETAK MERENJA (START MARKER)
    // ==========================================
    *marker = 0x11111111; 

    // Resetuj akcelerator (postavljanje done_reg na 0)
    IOWR_32DIRECT(WRAPPER_BASE, 0, 0x02);

    // Puni FIFO-e podacima (sa dummy ciklusom za kasnjenje)
    IOWR_32DIRECT(FIFO_A_BASE, 0, 0);
    IOWR_32DIRECT(FIFO_B_BASE, 0, 0);

    // Slanje elemenata matrica (pakovanje po dva elementa)
    IOWR_32DIRECT(FIFO_A_BASE, 0, pack_to_32bit(matA[0][0], 0));
    IOWR_32DIRECT(FIFO_B_BASE, 0, pack_to_32bit(matB[0][0], 0));

    IOWR_32DIRECT(FIFO_A_BASE, 0, pack_to_32bit(matA[0][1], matA[1][0]));
    IOWR_32DIRECT(FIFO_B_BASE, 0, pack_to_32bit(matB[1][0], matB[0][1]));

    IOWR_32DIRECT(FIFO_A_BASE, 0, pack_to_32bit(0, matA[1][1]));
    IOWR_32DIRECT(FIFO_B_BASE, 0, pack_to_32bit(0, matB[1][1]));

    //dummy podaci na kraju)
    IOWR_32DIRECT(FIFO_A_BASE, 0, 0);
    IOWR_32DIRECT(FIFO_B_BASE, 0, 0);

    // START: Pokretanje hardverskog izračunavanja
    IOWR_32DIRECT(WRAPPER_BASE, 0, 0x01);

    // Čekaj dok hardver ne podigne 'done' flag (bit 1)
    while (!(IORD_32DIRECT(WRAPPER_BASE, 0) & 0x02)); //

    // ==========================================
    // KORAK 2: KRAJ MERENJA (STOP MARKER)
    // ==========================================
    *marker = 0x22222222; 

    // Opciono: Čitanje rezultata iz FIFO C i obrada
    uint32_t w0 = IORD_32DIRECT(FIFO_C_BASE, 0);
    uint32_t w1 = IORD_32DIRECT(FIFO_C_BASE, 0);
    uint32_t w2 = IORD_32DIRECT(FIFO_C_BASE, 0);

    // Ovde možeš dodati extract_24bit ako želiš da ispišeš brojeve,
    // ali za merenje performansi smo završili posao.

    while(1); // Beskonačna petlja 
    return 0; 
}

/*
#include <stdint.h>

#define RESULT_PTR 0x0001FF00

int main() {

    volatile int8_t matA[2][2] = {{1, 2}, {3, 4}};
    volatile int8_t matB[2][2] = {{5, 6}, {7, 8}};
    volatile int32_t matC[2][2];
    
    volatile uint32_t *marker = (uint32_t *)RESULT_PTR;

    // --- KORAK 1: START MARKER ---
    *marker = 0x11111111; 

    // --- KORAK 2: SOFTVERSKO MNOŽENJE ---
    for (int i = 0; i < 2; i++) {
        for (int j = 0; j < 2; j++) {
            int32_t sum = 0;
            for (int k = 0; k < 2; k++) {
                sum += (int32_t)matA[i][k] * (int32_t)matB[k][j];
            }
            matC[i][j] = sum;
        }
    }

    // --- KORAK 3: STOP MARKER ---
    *marker = 0x22222222; 

    while(1); 
    return 0;
}*/