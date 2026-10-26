/** Thrown when a module is used before its init function ran. */
export class ModuleUninitialized extends Error {
    constructor(moduleName: string, initName: string) {
        super(`${moduleName} is uninitialized. Please run ${initName}() before referencing.`);
        this.name = 'ModuleUninitialized';

        // Set the prototype explicitly to maintain the correct prototype chain
        Object.setPrototypeOf(this, ModuleUninitialized.prototype);
    }
}