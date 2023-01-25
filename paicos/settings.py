# Boolean determining whether we use Paicos quantities as a default
use_units = True

# Number of threads to use in calculations
numthreads = 16

# Settings for automatic calculation of derived variables
use_only_user_functions = False
print_info_when_deriving_variables = True

# Load all fields as double precision arrays (FALSE is currently not supported
# by the Cython routines, so True is strongly recommended)
double_precision = True