#!/usr/bin/python3
import os, sys, subprocess, base64, webbrowser
_thisdir = os.path.split(os.path.abspath(__file__))[0]

ZIG = os.path.join(_thisdir, 'zig-linux-x86_64-0.13.0/zig')

if not os.path.isfile(ZIG):
	if not os.path.isfile('zig-linux-x86_64-0.13.0.tar.xz'):
		cmd = 'wget -c https://ziglang.org/download/0.13.0/zig-linux-x86_64-0.13.0.tar.xz'
		print(cmd)
		subprocess.check_call(cmd.split())
	cmd = 'tar -xvf zig-linux-x86_64-0.13.0.tar.xz'
	print(cmd)
	subprocess.check_call(cmd.split())

ZIG_VER = subprocess.check_output([ZIG, 'version']).decode('utf-8')
print('zig version:', ZIG_VER)


TEST = r'''
const std = @import("std");
pub fn main() !void {
	std.debug.print("Hello, World!\n", .{});
}
'''

def test_native():
	tmp = '/tmp/test-zig.zig'
	open(tmp, 'w').write(TEST)
	cmd = [ZIG, 'build-exe', tmp]
	print(cmd)
	subprocess.check_call(cmd, cwd='/tmp')

	cmd = ['/tmp/test-zig']
	print(cmd)
	subprocess.check_call(cmd)

TEST_WASM = r'''
extern fn foo() void;
pub fn main() !void {
	foo();
}
'''

TEST_WASM_MIN = r'''
export fn myfunc() c_int {
	return 1;
}
pub fn main() void{
	
}
'''

## https://www.reddit.com/r/Zig/comments/1eony2f/wasm_build_size_is_huge/
def test_wasm( freestanding=True):
	cmd = [ZIG, 'build-exe']
	target = 'wasm32-wasi'
	tmp = '/tmp/test-wasm-zig.zig'
	if freestanding:
		target = 'wasm32-freestanding-musl'
		tmp = '/tmp/test-wasm-freestanding-zig.zig'

	open(tmp, 'w').write(TEST_WASM)
	cmd += [ '-O', 'ReleaseSmall', '-target', target,  tmp]
	print(cmd)
	subprocess.check_call(cmd, cwd='/tmp')

	os.system('ls -l /tmp/*.wasm')

JS_API = '''
function make_environment(e){
	return new Proxy(e,{
		get(t,p,r) {
			if(e[p]!==undefined){return e[p].bind(e)}
			return(...args)=>{throw p}
		}
	});
}

class api {
	proxy(){
		return make_environment(this)
	}
	reset(wasm,id,bytes){
		this.elts=[];
		this.wasm=wasm;
		this.bytes=new Uint8Array(bytes);
		this.canvas=document.getElementById(id);
		this.ctx=this.canvas.getContext('2d');
		this.wasm.instance.exports.main();
		const f=(ts)=>{
			this.dt=(ts-this.prev)/1000;
			this.prev=ts;
			this.entryFunction();
			window.requestAnimationFrame(f)
		};
		window.requestAnimationFrame((ts)=>{
			this.prev=ts;
			window.requestAnimationFrame(f)
		});
	}
	foo() {
		window.alert("hello from zig")
	}

}

var $ = new api();
'''

JS_DECOMP = '''
var $d=async(u,t)=>{
	var d=new DecompressionStream('gzip')
	var r=await fetch('data:application/octet-stream;base64,'+u)
	var b=await r.blob()
	var s=b.stream().pipeThrough(d)
	var o=await new Response(s).blob()
	if(t) return await o.text()
	else return await o.arrayBuffer()
}

$d($wasm).then((r)=>{
	console.log(r);
	WebAssembly.instantiate(r,{env:$.proxy()}).then((c)=>{$.reset(c,"$",r)});
});

'''

TEST_WASM_JS = r'''
extern fn foo() void;
export fn main() void {
	foo();
}
'''

def build():
	name = 'test-wasm-foo'
	tmp = '/tmp/%s.zig' % name
	open(tmp, 'w').write(TEST_WASM_JS)
	cmd = [
		ZIG, 'build-exe', 
		'-O', 'ReleaseSmall', 
		'-target', 'wasm32-freestanding-musl',
		'-fno-entry',
		'--export-table', '-rdynamic',
		'--initial-memory=%s' % (1024*1024),
		tmp
	]
	print(cmd)
	subprocess.check_call(cmd, cwd='/tmp')

	os.system('ls -l /tmp/*.wasm')

	wasm = '/tmp/%s.wasm' % name
	cmd = ['gzip', '--keep', '--force', '--verbose', '--best', wasm]
	print(cmd)
	subprocess.check_call(cmd)
	wa = open(wasm,'rb').read()
	w = open(wasm+'.gz','rb').read()
	b = base64.b64encode(w).decode('utf-8')


	o = [
		'<html>',
		'<body>',
		'<canvas id="$"></canvas>',
		'<script>', 
		JS_API,
		'var $wasm="%s"' % b,
		JS_DECOMP,
		'</script>',
	]

	out = 'zigblender.html'
	open(out,'w').write('\n'.join(o))
	webbrowser.open(out)

if __name__=='__main__':
	if '--help' in sys.argv:
		subprocess.check_call([ZIG, '--help'])
		subprocess.check_call([ZIG, 'build-exe', '--help'])
		targets = subprocess.check_output([ZIG, 'targets']).decode('utf-8')
		for ln in targets.splitlines():
			if 'wasm' in ln:
				print(ln)
			if 'freestanding' in ln:
				print(ln)
		sys.exit()

	elif '--native' in sys.argv:
		test_native()
	else:
		test_wasm()


	#cmd = [ZIG, 'build', '--verbose']
	#subprocess.check_call(cmd)
	#minimal-zig-wasm-canvas/build.zig:13:33: error: no field named 'path' in union 'Build.LazyPath'
	#        .root_source_file = .{ .path = "src/checkerboard.zig" },
	#                                ^~~~
	#zig-linux-x86_64-0.13.0/lib/std/Build.zig:2171:22: note: union declared here
	#pub const LazyPath = union(enum) {                     ^~~~~
	#referenced by:
	#    runBuild__anon_8819: zig-linux-x86_64-0.13.0/lib/std/Build.zig:2116:27
	#    main: zig-linux-x86_64-0.13.0/lib/compiler/build_runner.zig:301:29
	build()

