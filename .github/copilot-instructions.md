- Name unit tests according to the requirement that is tested, e.g.    
  test_my_function_shall_raise_an_exception_if_invalid_parameters_are_given
  or test_shall_do_something_if_some_condition. 

- For naming unit tests, omit the name of the function under test if it is mentioned in 
  the test suite or test class.

- Keep the names of unit tests shorter than 80 characters.

- If a variable has a unit, then add a unit postfix to a variable name, e.g.
  distance_m, time_s, speed_kmh, temperature_c, pressure_pa, energy_j, money_eur, 
  money_usd. 

- Prefer SI and other internationally standardized units over imperial units 
  and units exclusively used in the US.

- Do not repeat default variable values in docstrings.

- Do not repeat types of variables in docstrings if they are already specified in type 
  hints.

  