library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.systolic_types.all;

entity systolic_st_wrapper is
    port (
        clk                : in  std_logic;
        rst                : in  std_logic;
        -- POPRAVLJENO: Magistrale automatski rastu i smanjuju se sa parametrima
        asi_a_data         : in  std_logic_vector(N*ELEM_WIDTH-1 downto 0);
        asi_a_valid        : in  std_logic;
        asi_a_ready        : out std_logic;
        asi_b_data         : in  std_logic_vector(N*ELEM_WIDTH-1 downto 0);
        asi_b_valid        : in  std_logic;
        asi_b_ready        : out std_logic;
        aso_c_data         : out std_logic_vector(N*N*ACC_WIDTH-1 downto 0);
        aso_c_valid        : out std_logic;
        aso_c_ready        : in  std_logic;
        avs_s0_address     : in  std_logic_vector(1 downto 0);
        avs_s0_read        : in  std_logic;
        avs_s0_readdata    : out std_logic_vector(31 downto 0);
        avs_s0_write       : in  std_logic;
        avs_s0_writedata   : in  std_logic_vector(31 downto 0);
        avs_s0_waitrequest : out std_logic
    );
end entity;

architecture rtl of systolic_st_wrapper is
    type state_t is (ST_IDLE, ST_CLEAR, ST_LOAD, ST_WAIT, ST_DONE);
    signal state : state_t := ST_IDLE;

    -- POPRAVLJENO: Skalabilna latencija (3*N pokriva maksimalni put kroz niz)
    constant TOTAL_LATENCY : integer := 3*N; 
    signal counter : integer range 0 to 127 := 0;

    signal clear_acc     : std_logic := '0';
    signal valid_to_sa   : std_logic := '0';
    signal a_in_vec      : vec_elem;
    signal b_in_vec      : vec_elem;
    signal c_out_mat     : mat_acc;

    signal start_reg      : std_logic := '0';
    signal done_reg       : std_logic := '0';
    signal input_count    : integer range 0 to 63 := 0;
begin
    avs_s0_waitrequest <= '0';

    asi_a_ready <= '1' when (state = ST_LOAD) else '0';
    asi_b_ready <= '1' when (state = ST_LOAD) else '0';

    -- Validacija slanja
    valid_to_sa <= '1' when (state = ST_LOAD and asi_a_valid = '1' and asi_b_valid = '1' and input_count > 0) else '0';
     
    clear_acc <= '1' when state = ST_CLEAR else '0';

    -- POPRAVLJENO: Parametarsko raspakivanje (MSB-first) nezavisno od širine bita i N
    gen_upk: for i in 0 to N-1 generate
        a_in_vec(i) <= signed(asi_a_data((N-i)*ELEM_WIDTH-1 downto (N-i-1)*ELEM_WIDTH));
        b_in_vec(i) <= signed(asi_b_data((N-i)*ELEM_WIDTH-1 downto (N-i-1)*ELEM_WIDTH));
    end generate;

    u_sa: entity work.systolic8x8
        port map(
            clk        => clk,
            rst        => rst,
            clear_acc  => clear_acc,
            A_in       => a_in_vec,
            B_in       => b_in_vec,
            valid_in   => valid_to_sa,
            C_out      => c_out_mat
        );

    gen_pk_i: for i in 0 to N-1 generate
        gen_pk_j: for j in 0 to N-1 generate
            aso_c_data(((i*N+j)+1)*ACC_WIDTH-1 downto (i*N+j)*ACC_WIDTH) <= 
                std_logic_vector(c_out_mat(i,j));
        end generate;
    end generate;

    process(clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                state     <= ST_IDLE;
                start_reg <= '0';
                done_reg  <= '0';
                counter   <= 0;
                input_count <= 0;
            else
                if avs_s0_write = '1' and avs_s0_address = "00" then
                    if avs_s0_writedata(0) = '1' then start_reg <= '1'; end if;
                    if avs_s0_writedata(1) = '1' then done_reg <= '0'; end if;
                end if;

                case state is
                    when ST_IDLE =>
                        if start_reg = '1' then
                            state <= ST_CLEAR;
                            start_reg <= '0';
                        end if;

                    when ST_CLEAR =>
                        counter   <= 0;
                        state     <= ST_LOAD;
                        input_count <= 0;

                    when ST_LOAD =>
                        if (asi_a_valid = '1' and asi_b_valid = '1') then
                            input_count <= input_count + 1;
                            -- Puni se kroz 2*N ciklusa proračuna
                            if input_count = (2*N) then
                                 state       <= ST_WAIT;
                                 input_count <= 0;
                                 counter     <= 0;
                            end if;
                        end if;

                    when ST_WAIT =>
                        if counter = TOTAL_LATENCY then
                            state    <= ST_DONE;
                            done_reg <= '1';
                            counter  <= 0;
                        else
                            counter <= counter + 1;
                        end if;

                    when ST_DONE =>
                        done_reg <= '1';
                        if aso_c_ready = '1' then
                            state <= ST_IDLE;
                        end if;
                end case;
            end if;
        end if;
    end process;

    aso_c_valid <= '1' when state = ST_DONE else '0';

    process(avs_s0_read, avs_s0_address, start_reg, done_reg)
    begin
        avs_s0_readdata <= (others => '0');
        if avs_s0_read = '1' and avs_s0_address = "00" then
            avs_s0_readdata(0) <= start_reg;
            avs_s0_readdata(1) <= done_reg;
        end if;
    end process;
    
end architecture;
