import os
import sys
import math
import random

import pygame

from scripts.utils import load_image, load_images, Animation
from scripts.entities import PhysicsEntity, Player, Enemy
from scripts.tilemap import Tilemap
from scripts.clouds import Clouds
from scripts.particle import Particle
from scripts.spark import Spark

class Game:
    def __init__(self):
        pygame.init()

        pygame.display.set_caption('ninja game')
        self.screen = pygame.display.set_mode((640, 480))
        self.display = pygame.Surface((320, 240), pygame.SRCALPHA)
        self.display_2 = pygame.Surface((320, 240))

        self.clock = pygame.time.Clock()
        
        # --- ASSETS & UI ---
        self.font = pygame.font.SysFont('Arial', 16, bold=True)
        self.title_font = pygame.font.SysFont('Arial', 32, bold=True)
        self.menu = True
        self.game_over = False # Added Game Over state
        self.victory = False  # To distinguish between Win/Loss
        self.show_controls = False 
        self.menu_timer = 0
        self.current_music = None 
        
        # Life System
        self.lives = 3 
        
        self.level_time = 0
        self.paused = False
        self.movement = [False, False]
        
        self.assets = {
            'decor': load_images('tiles/decor'),
            'grass': load_images('tiles/grass'),
            'large_decor': load_images('tiles/large_decor'),
            'stone': load_images('tiles/stone'),
            'player': load_image('entities/player.png'),
            'backgrounds': [
                load_image('background.png'),
                load_image('background_1.png'),
                load_image('background_2.png')
            ],
            'clouds': load_images('clouds'),
            'enemy/idle': Animation(load_images('entities/enemy/idle'), img_dur=6),
            'enemy/run': Animation(load_images('entities/enemy/run'), img_dur=4),
            'player/idle': Animation(load_images('entities/player/idle'), img_dur=6),
            'player/run': Animation(load_images('entities/player/run'), img_dur=4),
            'player/jump': Animation(load_images('entities/player/jump')),
            'player/slide': Animation(load_images('entities/player/slide')),
            'player/wall_slide': Animation(load_images('entities/player/wall_slide')),
            'particle/leaf': Animation(load_images('particles/leaf'), img_dur=20, loop=False),
            'particle/particle': Animation(load_images('particles/particle'), img_dur=6, loop=False),
            'gun': load_image('gun.png'),
            'projectile': load_image('projectile.png'),
        }
        
        self.sfx = {
            'jump': pygame.mixer.Sound('data/sfx/jump.wav'),
            'dash': pygame.mixer.Sound('data/sfx/dash.wav'),
            'hit': pygame.mixer.Sound('data/sfx/hit.wav'),
            'shoot': pygame.mixer.Sound('data/sfx/shoot.wav'),
            'ambience': pygame.mixer.Sound('data/sfx/ambience.wav'),
        }
        
        self.sfx['ambience'].set_volume(0.2)
        self.sfx['shoot'].set_volume(0.4)
        self.sfx['hit'].set_volume(0.8)
        self.sfx['dash'].set_volume(0.3)
        self.sfx['jump'].set_volume(0.7)
        
        self.clouds = Clouds(self.assets['clouds'], count=16)
        self.player = Player(self, (50, 50), (8, 15))
        self.tilemap = Tilemap(self, tile_size=16)
        
        self.level = 0
        self.load_level(self.level)
        self.screenshake = 0
        self.transition = 0 
        
    def load_level(self, map_id):
        self.tilemap.load('data/maps/' + str(map_id) + '.json')
        self.leaf_spawners = []
        for tree in self.tilemap.extract([('large_decor', 2)], keep=True):
            self.leaf_spawners.append(pygame.Rect(4 + tree['pos'][0], 4 + tree['pos'][1], 23, 13))
            
        self.enemies = []
        for spawner in self.tilemap.extract([('spawners', 0), ('spawners', 1)]):
            if spawner['variant'] == 0:
                self.player.pos = spawner['pos']
                self.player.air_time = 0
            else:
                self.enemies.append(Enemy(self, spawner['pos'], (8, 15)))
            
        self.projectiles = []
        self.particles = []
        self.sparks = []
        self.scroll = [0, 0]
        self.dead = 0
        self.transition = -30
        self.level_time = 0
        
    def format_time(self, frames):
        total_seconds = frames / 60
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int((total_seconds % 1) * 100)
        return f"{minutes:02}:{seconds:02}.{milliseconds:02}"

    def reset_game(self):
        self.lives = 3
        self.level = 0
        self.game_over = False
        self.victory = False
        self.menu = True
        self.load_level(self.level)
        
    def run(self):
        self.sfx['ambience'].play(-1)
        
        while True:
            if self.menu or self.game_over:
                if self.current_music != 'menu':
                    if os.path.exists('data/menu_music.ogg'):
                        pygame.mixer.music.load('data/menu_music.ogg')
                        pygame.mixer.music.set_volume(0.5)
                        pygame.mixer.music.play(-1)
                        self.current_music = 'menu'
            else:
                if self.current_music != 'game':
                    if os.path.exists('data/music.wav'):
                        pygame.mixer.music.load('data/music.wav')
                        pygame.mixer.music.set_volume(0.5)   
                        pygame.mixer.music.play(-1)
                        self.current_music = 'game'

            self.display.fill((0, 0, 0, 0))
            bg_idx = min(self.level, len(self.assets['backgrounds']) - 1)
            self.display_2.blit(self.assets['backgrounds'][bg_idx], (0, 0))
            
            self.menu_timer += 1
            render_scroll = (int(self.scroll[0]), int(self.scroll[1]))
            
            # --- LOGIC ---
            if not self.menu and not self.paused and not self.game_over:
                self.screenshake = max(0, self.screenshake - 1)
                if not self.dead and self.transition <= 0:
                    self.level_time += 1

                # Check for Level Completion
                if not len(self.enemies):
                    self.transition += 1
                    if self.transition > 30:
                        if self.level >= 2: # End of 2.json
                            self.game_over = True
                            self.victory = True
                        else:
                            self.level += 1
                            self.load_level(self.level)

                if self.transition < 0:
                    self.transition += 1

                if self.dead:
                    self.dead += 1
                    if self.dead >= 10:
                        self.transition = min(30, self.transition + 1)
                    if self.dead > 40:
                        self.lives -= 1 
                        if self.lives <= 0:
                            self.game_over = True
                            self.victory = False
                        else:
                            self.load_level(self.level)
                
                self.scroll[0] += (self.player.rect().centerx - self.display.get_width() / 2 - self.scroll[0]) / 30
                self.scroll[1] += (self.player.rect().centery - self.display.get_height() / 2 - self.scroll[1]) / 30
                
                for rect in self.leaf_spawners:
                    if random.random() * 49999 < rect.width * rect.height:
                        pos = (rect.x + random.random() * rect.width, rect.y + random.random() * rect.height)
                        self.particles.append(Particle(self, 'leaf', pos, velocity=[-0.1, 0.3], frame=random.randint(0, 20)))
                
                self.clouds.update()
                for enemy in self.enemies.copy():
                    kill = enemy.update(self.tilemap, (0, 0))
                    if kill: self.enemies.remove(enemy)
                if not self.dead:
                    self.player.update(self.tilemap, (self.movement[1] - self.movement[0], 0))
                for projectile in self.projectiles.copy():
                    projectile[0][0] += projectile[1]
                    projectile[2] += 1
                    if self.tilemap.solid_check(projectile[0]):
                        self.projectiles.remove(projectile)
                        for i in range(4):
                            self.sparks.append(Spark(projectile[0], random.random() - 0.5 + (math.pi if projectile[1] > 0 else 0),
                                                      2 + random.random()))
                    elif projectile[2] > 360:
                        self.projectiles.remove(projectile)
                    elif abs(self.player.dashing) < 50:
                        if self.player.rect().collidepoint(projectile[0]):
                            self.projectiles.remove(projectile)
                            self.dead += 1
                            self.sfx['hit'].play()
                            self.screenshake = max(16, self.screenshake)
                            for i in range(30):
                                angle = random.random() * math.pi * 2
                                speed = random.random() * 5
                                self.sparks.append(Spark(self.player.rect().center, angle, 2 + random.random()))
                                self.particles.append(Particle(self, 'particle', self.player.rect().center, velocity=[math.cos(angle + math.pi) * speed * 0.5, 
                                                                                                                      math.sin(angle + math.pi) * 
                                speed * 0.5], frame=random.randint(0, 7)))
                for spark in self.sparks.copy():
                    if spark.update(): self.sparks.remove(spark)
                for particle in self.particles.copy():
                    kill = particle.update()
                    if particle.type == 'leaf':
                        particle.pos[0] += math.sin(particle.animation.frame * 0.035) * 0.3
                    if kill: self.particles.remove(particle)

            # --- RENDER ---
            self.clouds.render(self.display_2, offset=render_scroll)
            self.tilemap.render(self.display, offset=render_scroll)
            for enemy in self.enemies:
                enemy.render(self.display, offset=render_scroll)
            if not self.dead:
                self.player.render(self.display, offset=render_scroll)
            for projectile in self.projectiles:
                img = self.assets['projectile']
                self.display.blit(img, (projectile[0][0] - img.get_width() / 2 - render_scroll[0], projectile[0][1] - img.get_height() / 2 - render_scroll[1]))
            for spark in self.sparks:
                spark.render(self.display, offset=render_scroll)
            for particle in self.particles:
                particle.render(self.display, offset=render_scroll)

            display_mask = pygame.mask.from_surface(self.display)
            display_silhouette = display_mask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))
            for offset in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                self.display_2.blit(display_silhouette, offset)
            self.display_2.blit(self.display, (0, 0))

            if not self.menu and not self.game_over:
                lives_surf = self.font.render(f"LIVES: {self.lives}", True, (255, 100, 100))
                self.display_2.blit(lives_surf, (10, 10))
                time_surf = self.font.render(self.format_time(self.level_time), False, (255, 255, 255))
                self.display_2.blit(time_surf, (self.display.get_width() - time_surf.get_width() - 10, 10))

            # --- MENU DESIGN ---
            if self.menu:
                menu_fade = pygame.Surface(self.display.get_size(), pygame.SRCALPHA)
                menu_fade.fill((10, 10, 20, 200)) 
                self.display_2.blit(menu_fade, (0, 0))
                
                box_rect = pygame.Rect(self.display.get_width()//2 - 100, 40, 200, 140)
                pygame.draw.rect(self.display_2, (30, 30, 50), box_rect)
                pygame.draw.rect(self.display_2, (255, 255, 255), box_rect, 2) 

                if self.show_controls:
                    controls_title = self.font.render("CONTROLS", True, (255, 255, 0))
                    self.display_2.blit(controls_title, (self.display.get_width()//2 - controls_title.get_width()//2, 50))
                    control_list = ["WASD - MOVE / JUMP", "SHIFT - DASH", "P - PAUSE", "ESC - BACK"]
                    for i, line in enumerate(control_list):
                        line_surf = self.font.render(line, True, (255, 255, 255))
                        self.display_2.blit(line_surf, (self.display.get_width()//2 - line_surf.get_width()//2, 80 + i * 20))
                else:
                    title_y = 60 + math.sin(self.menu_timer * 0.05) * 4
                    title_surf = self.title_font.render("NINJA GAME", True, (255, 255, 255))
                    self.display_2.blit(title_surf, (self.display.get_width()//2 - title_surf.get_width()//2, title_y))
                    
                    if (self.menu_timer // 30) % 2:
                        start_surf = self.font.render("SPACE TO START", True, (0, 255, 180))
                        self.display_2.blit(start_surf, (self.display.get_width()//2 - start_surf.get_width()//2, 115))
                        ctrl_hint_surf = self.font.render("'I' FOR CONTROLS", True, (0, 200, 255))
                        self.display_2.blit(ctrl_hint_surf, (self.display.get_width()//2 - ctrl_hint_surf.get_width()//2, 135))
                    
                    ver_surf = self.font.render("Created By Aayan Mir", True, (150, 150, 150))
                    self.display_2.blit(ver_surf, (self.display.get_width()//2 - ver_surf.get_width()//2, 162))

            # --- NEW GAME OVER DESIGN ---
            elif self.game_over:
                menu_fade = pygame.Surface(self.display.get_size(), pygame.SRCALPHA)
                menu_fade.fill((20, 10, 10, 220)) 
                self.display_2.blit(menu_fade, (0, 0))
                
                msg = "MISSION COMPLETE" if self.victory else "NINJA DEFEATED"
                color = (0, 255, 150) if self.victory else (255, 50, 50)
                
                go_surf = self.title_font.render(msg, True, color)
                self.display_2.blit(go_surf, (self.display.get_width()//2 - go_surf.get_width()//2, 80))
                
                restart_surf = self.font.render("PRESS SPACE TO RETURN TO MENU", True, (255, 255, 255))
                self.display_2.blit(restart_surf, (self.display.get_width()//2 - restart_surf.get_width()//2, 140))

            elif self.paused:
                pause_text = self.font.render("PAUSED", True, (255, 255, 0))
                self.display_2.blit(pause_text, (self.display.get_width() // 2 - pause_text.get_width() // 2, self.display.get_height() // 2))

            if self.transition and not self.menu and not self.game_over:
                transition_surf = pygame.Surface(self.display.get_size())
                transition_surf.fill((0, 0, 0))
                pygame.draw.circle(transition_surf, (255, 255, 255), (self.display.get_width() // 2, self.display.get_height() // 2), max(0, (30 - abs(self.transition)) * 8))
                transition_surf.set_colorkey((255, 255, 255))
                self.display_2.blit(transition_surf, (0, 0))

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if self.menu:
                        if event.key == pygame.K_i:
                            self.show_controls = True
                        if event.key == pygame.K_ESCAPE:
                            self.show_controls = False
                        if event.key == pygame.K_SPACE:
                            if not self.show_controls:
                                self.menu = False
                                self.transition = 0
                    
                    elif self.game_over:
                        if event.key == pygame.K_SPACE:
                            self.reset_game() # Back to menu

                    else:
                        if event.key == pygame.K_p:
                            self.paused = not self.paused
                        if not self.paused:
                            if event.key == pygame.K_a: self.movement[0] = True
                            if event.key == pygame.K_d: self.movement[1] = True
                            if event.key == pygame.K_w or event.key == pygame.K_SPACE:
                                if self.player.jump():
                                    self.sfx['jump'].play()
                            if event.key == pygame.K_LSHIFT: self.player.dash()
                if event.type == pygame.KEYUP:
                    if event.key == pygame.K_a: self.movement[0] = False
                    if event.key == pygame.K_d: self.movement[1] = False
                        
            screenshake_offset = (random.random() * self.screenshake - self.screenshake / 2, random.random() * self.screenshake - self.screenshake / 2)
            self.screen.blit(pygame.transform.scale(self.display_2, self.screen.get_size()), screenshake_offset)
            pygame.display.update()
            self.clock.tick(60)

Game().run()