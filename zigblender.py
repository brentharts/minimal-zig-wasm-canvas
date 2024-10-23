#!/usr/bin/python3
import os, sys, subprocess, base64, webbrowser
_thisdir = os.path.split(os.path.abspath(__file__))[0]

if sys.platform == 'win32':
	BLENDER = 'C:/Program Files/Blender Foundation/Blender 4.2/blender.exe'
elif sys.platform == 'darwin':
	BLENDER = '/Applications/Blender.app/Contents/MacOS/Blender'
else:
	BLENDER = 'blender'

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

	rect(x,y,w,h, r,g,b,a){
		this.ctx.fillStyle='rgba('+r+','+g+','+b+','+a+')';
		this.ctx.fillRect(x,y,w,h)
	}


}

var $=new api();
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


TEST_WASM_CANVAS = r'''
extern fn rect(x:c_int,y:c_int, w:c_int,h:c_int, r:u8,g:u8,b:u8, alpha:f32 ) void;

export fn main() void {
	for (0..8) |y| {
		for (0..8) |x| {
			rect( @intCast(x*64),@intCast(y*64), 32,32, 200,0,0, 1.0);
		}
	}
}
'''


def build(zig):
	name = 'test-wasm-foo'
	tmp = '/tmp/%s.zig' % name
	open(tmp, 'w').write(zig)
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

try:
	import bpy
except:
	bpy = None


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

	elif '--test-native' in sys.argv:
		test_native()
		sys.exit()
	elif '--test-wasm' in sys.argv:
		test_wasm()
		sys.exit()
	elif '--test-wasm-canvas' in sys.argv:
		build(TEST_WASM_CANVAS)
	elif bpy:
		pass
	else:
		cmd = [BLENDER]
		for arg in sys.argv:
			if arg.endswith('.blend'):
				cmd.append(arg)
				break
		cmd +=['--python-exit-code', '1', '--python', __file__]
		exargs = []
		for arg in sys.argv:
			if arg.startswith('--'):
				exargs.append(arg)
		if exargs:
			cmd.append('--')
			cmd += exargs
		print(cmd)
		subprocess.check_call(cmd)
		sys.exit()

## in blender ##
import math, mathutils
from random import random, uniform

@bpy.utils.register_class
class C3Export(bpy.types.Operator):
	bl_idname = "c3.export_wasm"
	bl_label = "C3 Export WASM"
	@classmethod
	def poll(cls, context):
		return True
	def execute(self, context):
		build_wasm(context.world)
		return {"FINISHED"}


@bpy.utils.register_class
class ZigWorldPanel(bpy.types.Panel):
	bl_idname = "WORLD_PT_ZigWorld_Panel"
	bl_label = "Zig Export"
	bl_space_type = "PROPERTIES"
	bl_region_type = "WINDOW"
	bl_context = "world"

	def draw(self, context):
		self.layout.operator("zig.export_wasm", icon="CONSOLE")


def safename(ob):
	return ob.name.lower().replace('.', '_')

ZIG_HEADER = '''
extern fn rect(x:c_int,y:c_int, w:c_int,h:c_int, r:u8,g:u8,b:u8, alpha:f32 ) void;

'''

def blender_to_c3(world):
	head = [ZIG_HEADER]
	setup = []
	draw = ['export fn main() void {']
	for ob in bpy.data.objects:
		if ob.hide_get(): continue
		print(ob)
		sname = safename(ob)
		if ob.type=='MESH':
			if len(ob.data.vertices)==4: ## assume plane
				x,y,z = ob.location
				z = int(-z)
				x = int(x)

				sx,sy,sz = ob.scale
				w = int(sx*2)
				h = int(sy*2)

				r,g,b,a = ob.color
				r = int(r*255)
				g = int(g*255)
				b = int(b*255)
				draw += [
					'	rect( %s,%s, %s,%s, %s,%s,%s, %s);' %(x,z,w,h,r,g,b,a),

				]

	draw.append('}')

	return '\n'.join(head+setup+draw)


def build_wasm(world):
	zig = blender_to_c3(world)
	print(zig)
	build(zig)


def test_scene():
	for y in range(8):
		for x in range(8):
			bpy.ops.mesh.primitive_plane_add()
			ob = bpy.context.active_object
			ob.location.x = x*64
			ob.location.z = -y*64
			ob.scale = [16,16,0]
			ob.rotation_euler.x = math.pi/2
			ob.color = [1,0,y*0.1,1]

if __name__=='__main__':
	test_scene()
	build_wasm(bpy.data.worlds[0])
