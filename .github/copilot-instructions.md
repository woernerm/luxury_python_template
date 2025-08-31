- For unit tests, name all test functions according to the requirement that is being
tested, e.g. def test_my_function_shall_raise_an_exception_if_invalid_parameters_are_given
or def test_shall_do_something_when_some_condition. The name of the function shall be
included only if it is not mentioned in the name of the test suite or the test class.
Keep the name shorter than 80 characters.

- If the unit of a variable is important, add a unit postfix to the variable name, e.g.
distance_m, time_s, speed_kmh, temperature_c, pressure_pa, energy_j, money_eur, 
money_usd. Prefer SI and other internationally standardized units over imperial units 
and units exclusively used in the US.