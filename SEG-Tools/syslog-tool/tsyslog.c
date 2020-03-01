#include <linux/module.h>
#include <linux/kernel.h>

static char* mystring = "blah....";
module_param(mystring, charp, 0000);
MODULE_PARM_DESC(mystring, "A character string");

int init_module(void) {
	printk(KERN_ERR "%s\n",mystring);
	return 0;
}

void cleanup_module(void) {
}
